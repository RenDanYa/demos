# -*- coding: utf-8 -*-
"""
小红书采集脚本
- tkinter 弹窗输入关键词
- 调用 opencli xiaohongshu search/note/comments/download
- 输出 Markdown 到 d:/obsidian/demo/05_long_project/小红书/{关键词}/
- 防风控: 5-8秒间隔 + 每50条批次休息 + 连续3次失败暂停
"""
import sys
import os
import json
import re
import time
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# 解析 opencli 调用方式
# Windows 下 .cmd 文件经 cmd.exe 调用会因 URL 中的 & 触发命令分隔,
# 因此直接用 node 调用 main.js 入口绕过 cmd.exe
def _resolve_opencli():
    npm_root = os.environ.get("APPDATA", "")
    npm_dir = Path(npm_root) / "npm" if npm_root else None

    # 优先: 直接 node + main.js (避免 cmd.exe 解析 &)
    if npm_dir:
        main_js = npm_dir / "node_modules" / "@jackwener" / "opencli" / "dist" / "src" / "main.js"
        if main_js.exists():
            node_bin = shutil.which("node") or "node"
            return ("node", str(main_js))

    # 回退 1: opencli 可执行文件 (Linux/Mac 或 Windows PATH 中)
    path = shutil.which("opencli")
    if path:
        return (path,)

    # 回退 2: 直接 .cmd (有 & 风险, 仅作最后手段)
    if npm_dir:
        cmd_file = npm_dir / "opencli.cmd"
        if cmd_file.exists():
            return (str(cmd_file),)

    return ("opencli",)  # 让 subprocess 报错

OPENCLI_CMD = _resolve_opencli()

# tkinter (Windows 自带)
try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False

# ============ 配置 ============
OBSIDIAN_ROOT = Path("d:/obsidian/demo")
OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "小红书"
LOG_FILE = OUTPUT_ROOT / "_运行日志.md"
SCRIPT_DIR = Path(__file__).parent

# 防风控参数 (复用项目约定)
INTERVAL_MIN = 5
INTERVAL_MAX = 8
BATCH_SIZE = 50
BATCH_REST_MIN = 30
BATCH_REST_MAX = 60
FAIL_THRESHOLD = 3
FAIL_PAUSE_MIN = 60
FAIL_PAUSE_MAX = 120

# 子进程超时 (秒)
TIMEOUT_SEARCH = 60
TIMEOUT_NOTE = 30
TIMEOUT_COMMENTS = 30
TIMEOUT_DOWNLOAD = 120


def log(msg):
    """统一日志输出 (utf-8 安全, 处理 Windows GBK 控制台)"""
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        # Windows 控制台 GBK 无法编码 emoji 等, 替换为 ?
        safe = line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace")
        print(safe, flush=True)


def show_input_dialog():
    """tkinter 弹窗: 关键词 + 数量"""
    if not HAS_TK:
        # 无 tkinter 时回退到命令行参数
        if len(sys.argv) >= 2:
            kw = sys.argv[1]
            limit = int(sys.argv[2]) if len(sys.argv) >= 3 else 10
            return kw, limit
        return None, None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    kw = simpledialog.askstring(
        "小红书采集",
        "请输入搜索关键词:",
        initialvalue="obsidian",
        parent=root,
    )
    if not kw or not kw.strip():
        root.destroy()
        return None, None
    kw = kw.strip()

    limit_str = simpledialog.askstring(
        "采集数量",
        f"采集「{kw}」前几条? (1-50)",
        initialvalue="10",
        parent=root,
    )
    try:
        limit = max(1, min(50, int(limit_str)))
    except (TypeError, ValueError):
        limit = 10

    root.destroy()
    return kw, limit


def run_opencli(args, timeout):
    """运行 opencli 命令, 返回 (success, stdout_dict_or_text, stderr)"""
    cmd = list(OPENCLI_CMD) + args
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            shell=False,
        )
        if result.returncode != 0:
            return False, None, result.stderr or f"exit code {result.returncode}"
        return True, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, None, "timeout"
    except FileNotFoundError:
        return False, None, f"opencli not found: {OPENCLI_CMD}. 安装: npm install -g @jackwener/opencli"
    except Exception as e:
        return False, None, str(e)


def parse_search_results(stdout):
    """解析 search -f json 输出 -> [{url, title, author, likes, ...}]"""
    try:
        data = json.loads(stdout)
        if not isinstance(data, list):
            return []
        # 过滤掉无 url 的项
        return [item for item in data if item.get("url")]
    except json.JSONDecodeError as e:
        log(f"  JSON 解析失败: {e}")
        return []


def parse_note_fields(stdout):
    """note 命令返回 [{field, value}] 数组, 转为 dict"""
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return {item.get("field", ""): item.get("value", "") for item in data if isinstance(item, dict)}
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as e:
        log(f"  note JSON 解析失败: {e}")
    return {}


def parse_comments(stdout):
    """解析 comments 输出"""
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError as e:
        log(f"  comments JSON 解析失败: {e}")
        return []


def extract_note_id(url):
    """从 URL 提取笔记 ID"""
    m = re.search(r"/(explore|search_result|discovery/item)/([a-f0-9]+)", url)
    if m:
        return m.group(2)
    # 回退: 取 path 最后一段
    parsed = urlparse(url)
    return Path(parsed.path).stem or "unknown"


def sanitize_filename(name):
    """清洗文件名: 移除 Windows 非法字符"""
    if not name:
        return "untitled"
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', "_", name)
    name = re.sub(r"_+", "_", name).strip("_ ")
    return name[:80]  # 限制长度


def parse_tags(tags_str):
    """解析 #tag1, #tag2 -> [tag1, tag2]"""
    if not tags_str:
        return []
    tags = re.findall(r"#([^\s#,]+)", tags_str)
    return [t.strip() for t in tags if t.strip()]


def search_notes(keyword, limit):
    """调用 opencli search"""
    log(f"搜索: {keyword} (limit={limit})")
    ok, stdout, err = run_opencli(
        ["xiaohongshu", "search", keyword, "--limit", str(limit), "-f", "json"],
        TIMEOUT_SEARCH,
    )
    if not ok:
        log(f"搜索失败: {err}")
        return []
    results = parse_search_results(stdout)
    log(f"搜索到 {len(results)} 条结果")
    return results[:limit]


def get_note(url):
    """调用 opencli note, 返回 dict"""
    ok, stdout, err = run_opencli(
        ["xiaohongshu", "note", url, "-f", "json"],
        TIMEOUT_NOTE,
    )
    if not ok:
        log(f"  note 失败: {err}")
        return None
    return parse_note_fields(stdout)


def get_comments(url):
    """调用 opencli comments"""
    ok, stdout, err = run_opencli(
        ["xiaohongshu", "comments", url, "-f", "json"],
        TIMEOUT_COMMENTS,
    )
    if not ok:
        log(f"  comments 失败: {err}")
        return []
    return parse_comments(stdout)


def download_images(url, output_dir):
    """调用 opencli download, 返回相对 output_dir 的图片路径列表"""
    # 清空并重建目录 (避免上次残留)
    import shutil as _shutil
    if output_dir.exists():
        _shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    ok, stdout, err = run_opencli(
        ["xiaohongshu", "download", url, "--output", str(output_dir)],
        TIMEOUT_DOWNLOAD,
    )
    if not ok:
        log(f"  download 失败: {err}")
    # 递归收集所有图片/视频文件 (opencli 会在 output_dir 下创建 {note_id}/ 子目录)
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov"}
    all_files = sorted(p for p in output_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts)
    rel_files = [str(p.relative_to(output_dir)).replace("\\", "/") for p in all_files]
    log(f"  download: files={len(rel_files)} ok={ok} dir={output_dir.name}")
    return rel_files


def build_markdown(keyword, note_data, comments, image_files, images_rel_dir, url, note_id, published_at=""):
    """生成 markdown 内容 (含 frontmatter)"""
    title = note_data.get("title", "无标题") or "无标题"
    author = note_data.get("author", "") or ""
    content = note_data.get("content", "") or ""
    likes = note_data.get("likes", "0") or "0"
    collects = note_data.get("collects", "") or ""
    comments_count = note_data.get("comments", "") or ""
    tags_str = note_data.get("tags", "") or ""
    tags = parse_tags(tags_str)
    # 发布日期 (来自 search 结果的 published_at)
    published = published_at or ""

    # 提取首图作为封面 (imageUrl 字段)
    image_cover = ""
    if image_files:
        image_cover = f"{images_rel_dir}/{image_files[0]}"

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # 提取数字点赞 (likes 可能是字符串)
    likes_num = 0
    try:
        likes_num = int(re.sub(r"[^\d]", "", str(likes)) or 0)
    except ValueError:
        pass

    # frontmatter (只保留核心属性)
    lines = ["---"]
    if tags:
        tags_yaml = ", ".join(f"\"{t}\"" for t in tags)
        lines.append(f"tags: [{tags_yaml}]")
    else:
        lines.append("tags: []")
    lines.append(f'title: "{title.replace(chr(34), chr(39))}"')
    lines.append(f"likes: {likes_num}")
    if published:
        lines.append(f'publishedAt: "{published}"')
    lines.append(f'url: "{url}"')
    if image_cover:
        lines.append(f'imageUrl: "{image_cover}"')
    lines.append(f"createTime: {now}")
    lines.append("status: 已采集")
    lines.append("---")
    lines.append("")

    # 标题
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> **作者**: {author} | **点赞**: {likes} | **收藏**: {collects} | **评论**: {comments_count}")
    lines.append(f"> **原链接**: {url}")
    lines.append("")

    # 正文
    if content:
        lines.append("## 正文")
        lines.append("")
        lines.append(content)
        lines.append("")

    # 图片
    if image_files:
        lines.append("## 图片")
        lines.append("")
        for img in image_files:
            lines.append(f"![|400]({images_rel_dir}/{img})")
        lines.append("")

    # 评论 (只保留前 5 条, 放在末尾)
    if comments:
        lines.append("## 评论")
        lines.append("")
        for i, c in enumerate(comments[:5], 1):
            if not isinstance(c, dict):
                continue
            c_author = c.get("author") or c.get("Author") or "匿名"
            c_text = c.get("text") or c.get("Text") or ""
            c_likes = c.get("likes") or c.get("Likes") or "0"
            c_time = c.get("time") or c.get("Time") or ""
            reply_tag = ""
            if c.get("is_reply") or c.get("Is_reply"):
                reply_to = c.get("reply_to") or c.get("Reply_to") or ""
                if reply_to:
                    reply_tag = f" ↳ 回复 @{reply_to}"
            lines.append(f"{i}. **{c_author}** ({c_likes}赞){reply_tag}: {c_text}")
            if c_time:
                lines.append(f"   - _{c_time}_")
        lines.append("")

    return "\n".join(lines)


def write_markdown(keyword, md_content, note_id, title=""):
    """写入 markdown 文件, 返回路径. 文件名优先用 title"""
    kw_dir = OUTPUT_ROOT / sanitize_filename(keyword)
    kw_dir.mkdir(parents=True, exist_ok=True)
    # 文件名: title 优先, 回退到 note_id
    name_base = sanitize_filename(title) if title else note_id
    if not name_base:
        name_base = note_id
    filename = f"{name_base}.md"
    md_path = kw_dir / filename
    # 若同名已存在, 加 note_id 后缀避免覆盖
    if md_path.exists():
        filename = f"{name_base}_{note_id}.md"
        md_path = kw_dir / filename
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def append_log(keyword, index, total, status, title, url, error="", path=""):
    """增量追加单条采集记录到日志 (防止进程被 kill 时日志全空)"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] [{index}/{total}] {status} | {title[:30]} | {url}"
    if error:
        line += f" | ERR: {error}"
    if path:
        line += f" | -> {Path(path).name}"
    line += "\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)


def init_log(keyword, limit):
    """开始采集时初始化日志文件 (覆盖旧内容, 写入表头)"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"# 小红书采集日志\n\n**开始时间**: {now}\n**关键词**: {keyword}\n**目标数量**: {limit}\n\n## 采集明细\n\n"
    LOG_FILE.write_text(header, encoding="utf-8")


def write_summary(keyword, results, elapsed):
    """追加汇总到日志末尾 (不覆盖明细)"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok_count = sum(1 for r in results if r["status"] == "ok")
    fail_count = len(results) - ok_count
    fail_list = [r for r in results if r["status"] != "ok"]

    lines = [
        "",
        "## 汇总",
        "",
        f"**完成时间**: {now}",
        f"**用时**: {elapsed:.0f}秒",
        f"**成功**: {ok_count} / {len(results)}",
        f"**失败**: {fail_count}",
        "",
    ]
    if fail_list:
        lines.append("### 失败列表")
        lines.append("")
        for r in fail_list:
            url = r.get("url", "?")
            err = r.get("error", "unknown")
            lines.append(f"- {url}: {err}")
        lines.append("")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"汇总已追加: {LOG_FILE}")


def collect(keyword, limit):
    """主采集流程"""
    search_results = search_notes(keyword, limit)
    if not search_results:
        log("无搜索结果, 退出")
        init_log(keyword, limit)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n无搜索结果\n")
        return []

    # 初始化日志 (覆盖旧内容)
    init_log(keyword, len(search_results))

    results = []
    consecutive_fails = 0
    images_root_name = sanitize_filename(keyword)
    total = len(search_results)

    for i, item in enumerate(search_results, 1):
        url = item.get("url", "")
        title = item.get("title", "?")
        log(f"[{i}/{total}] {title[:30]}...")

        # 间隔 (第 2 条起)
        if i > 1:
            wait = random.uniform(INTERVAL_MIN, INTERVAL_MAX)
            time.sleep(wait)

        # 批次休息
        if i > 1 and (i - 1) % BATCH_SIZE == 0:
            rest = random.uniform(BATCH_REST_MIN, BATCH_REST_MAX)
            log(f"  已处理 {i-1} 条, 批次休息 {rest:.0f} 秒...")
            time.sleep(rest)

        # 重试 3 次
        success = False
        last_err = ""
        for attempt in range(3):
            try:
                note_data = get_note(url)
                if not note_data:
                    raise RuntimeError("note 返回空")

                comments = get_comments(url)
                # comments 失败不阻断

                note_id = extract_note_id(url)
                images_dir = OUTPUT_ROOT / images_root_name / "images" / note_id
                # 相对于 markdown 文件所在目录 (OUTPUT_ROOT/{keyword}/) 的路径
                images_rel_dir = f"images/{note_id}"
                image_files = download_images(url, images_dir)

                md_content = build_markdown(
                    keyword, note_data, comments, image_files,
                    images_rel_dir, url, note_id,
                    published_at=item.get("published_at", ""),
                )
                md_title = note_data.get("title", "") or title
                md_path = write_markdown(keyword, md_content, note_id, title=md_title)
                log(f"  OK -> {md_path.name}")

                results.append({
                    "status": "ok",
                    "url": url,
                    "title": note_data.get("title", ""),
                    "path": str(md_path),
                })
                # 增量写入日志 (防止进程被 kill 时丢失)
                append_log(keyword, i, total, "OK", note_data.get("title", title), url, path=str(md_path))
                success = True
                consecutive_fails = 0
                break
            except Exception as e:
                last_err = str(e)
                log(f"  尝试 {attempt+1}/3 失败: {e}")
                if attempt < 2:
                    time.sleep(random.uniform(5, 10))

        if not success:
            results.append({
                "status": "fail",
                "url": url,
                "title": title,
                "error": last_err,
            })
            # 失败也记日志
            append_log(keyword, i, total, "FAIL", title, url, error=last_err)
            consecutive_fails += 1
            if consecutive_fails >= FAIL_THRESHOLD:
                pause = random.uniform(FAIL_PAUSE_MIN, FAIL_PAUSE_MAX)
                log(f"  连续失败 {consecutive_fails} 次, 暂停 {pause:.0f} 秒...")
                time.sleep(pause)
                consecutive_fails = 0

    return results


def main():
    log("=== 小红书采集脚本启动 ===")

    # 确保输出目录存在
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # 检查 opencli 是否可用
    ok, _, err = run_opencli(["--version"], 10)
    if not ok:
        msg = f"opencli 不可用: {err}\n安装: npm install -g @jackwener/opencli"
        log(msg)
        if HAS_TK:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("错误", msg)
            root.destroy()
        return 1

    keyword, limit = show_input_dialog()
    if not keyword:
        log("未输入关键词, 退出")
        return 0

    log(f"开始采集: keyword={keyword}, limit={limit}")
    start = time.time()
    results = []
    try:
        results = collect(keyword, limit)
    except Exception as e:
        # 异常兜底: 保留已采集的部分, 追加异常记录
        log(f"采集异常 (已采集 {len(results)} 条): {e}")
        append_log(keyword, len(results) + 1, limit, "EXCEPTION", "", "", error=f"collect 异常: {e}")
    elapsed = time.time() - start

    ok_count = sum(1 for r in results if r["status"] == "ok")
    log(f"=== 采集完成: 成功 {ok_count}/{len(results)}, 用时 {elapsed:.0f}s ===")

    # 追加汇总到日志末尾 (不覆盖增量明细)
    try:
        write_summary(keyword, results, elapsed)
    except Exception as e:
        log(f"写汇总日志失败: {e}")

    if HAS_TK:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "采集完成",
            f"关键词: {keyword}\n成功: {ok_count}/{len(results)}\n用时: {elapsed:.0f}秒\n日志: {LOG_FILE}",
        )
        root.destroy()

    return 0


if __name__ == "__main__":
    sys.exit(main())
