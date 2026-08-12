# -*- coding: utf-8 -*-
"""GitHub Topic 仓库采集

调用 opencli github topic 命令, 通过 GitHub Search API 获取指定 topic 下的
Top 仓库, 保存为 Obsidian Markdown 表格 (含中文翻译)。

对应 CLI: d:/voice/opencli-main/src/clis/github/topic.yaml
- 策略: public (无需浏览器桥接, 直接调用 GitHub API, 速度快)
- 输出列: rank, repo, stars, forks, language, description, url

用法:
    python github_topic.py                            # 弹窗输入 (topic/排序/数量/翻译)
    python github_topic.py                            # 默认: awesome/stars/20/翻译
    python github_topic.py machine-learning           # 指定 topic
    python github_topic.py react --sort updated       # 按 updated 排序
    python github_topic.py rust --limit 10            # 指定数量
    python github_topic.py awesome --no-translate     # 跳过翻译
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OPENCLI_CMD,
    OBSIDIAN_ROOT,
    log,
    run_opencli,
    sanitize_filename,
)
from github_trending import translate_descriptions  # noqa: E402

# ============ 配置 ============
OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "GitHub" / "Topic"
# public API 无需浏览器, 但 GitHub Search API 偶有延迟, 30 秒足够
TIMEOUT_TOPIC = 30

VALID_SORT = ("stars", "forks", "updated")
SORT_LABEL = {"stars": "Star 数", "forks": "Fork 数", "updated": "最近更新"}


def show_input_dialog():
    """tkinter 弹窗: topic / 排序 / 数量 / 翻译"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return None, None, None, None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    topic = simpledialog.askstring(
        "GitHub Topic",
        "Topic 名称 (例如 awesome/machine-learning/react):",
        initialvalue="awesome",
        parent=root,
    )
    if topic is None:
        root.destroy()
        return None, None, None, None
    topic = topic.strip()

    sort = simpledialog.askstring(
        "排序方式",
        "排序方式 (stars/forks/updated):",
        initialvalue="stars",
        parent=root,
    )
    if sort is None:
        root.destroy()
        return None, None, None, None
    sort = sort.strip().lower() or "stars"
    if sort not in VALID_SORT:
        sort = "stars"

    limit_str = simpledialog.askstring(
        "数量",
        "获取前几条? (1-100):",
        initialvalue="20",
        parent=root,
    )
    if limit_str is None:
        root.destroy()
        return None, None, None, None
    try:
        limit = max(1, min(100, int(limit_str)))
    except (TypeError, ValueError):
        limit = 20

    # 翻译选项: 输入 n 跳过, 其他视为启用
    translate_str = simpledialog.askstring(
        "翻译描述",
        "是否翻译描述为中文? (y/n, 默认 y):",
        initialvalue="y",
        parent=root,
    )
    root.destroy()
    translate = (translate_str or "y").strip().lower() != "n"

    return topic, sort, limit, translate


def parse_args():
    """命令行参数解析: topic [--sort x] [--limit n] [--no-translate]

    topic 为位置参数, 可放在任意 --option 之前。
    """
    topic = "awesome"
    sort = "stars"
    limit = 20
    translate = True

    args = sys.argv[1:]
    # 提取 flags
    if "--no-translate" in args:
        translate = False
        args = [a for a in args if a != "--no-translate"]

    # 提取 --sort
    if "--sort" in args:
        i = args.index("--sort")
        if i + 1 < len(args):
            s = args[i + 1].strip().lower()
            if s in VALID_SORT:
                sort = s
            args = args[:i] + args[i + 2:]

    # 提取 --limit
    if "--limit" in args:
        i = args.index("--limit")
        if i + 1 < len(args):
            try:
                limit = max(1, min(100, int(args[i + 1])))
            except ValueError:
                pass
            args = args[:i] + args[i + 2:]

    # 剩余第一个非空参数视为 topic
    for a in args:
        if a and not a.startswith("-"):
            topic = a.strip()
            break

    return topic, sort, limit, translate


def call_topic(topic, sort, limit):
    """调用 opencli github topic, 返回 list[dict] 或 None

    返回字段: rank, repo, stars, forks, language, description, url
    """
    args = [
        "github", "topic", topic,
        "--sort", sort,
        "--limit", str(limit),
        "-f", "json",
    ]

    ok, stdout, err = run_opencli(args, TIMEOUT_TOPIC)
    if not ok:
        log(f"topic 调用失败: {err}")
        return None

    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        log(f"topic 返回非数组: {type(data).__name__}")
        return []
    except json.JSONDecodeError as e:
        log(f"topic JSON 解析失败: {e}")
        log(f"原始 stdout 前 300 字符: {stdout[:300] if stdout else '(空)'}")
        return None


def fmt_num(n):
    """12345 -> 12.3k, 1200000 -> 1.2M"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n) if n else "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def build_markdown(topic, sort, limit, items, translate=False):
    """生成 markdown 内容

    items: [{rank, repo, stars, forks, language, description, url, description_zh?}, ...]
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sort_label = SORT_LABEL.get(sort, sort)
    title = f"GitHub Topic - {topic} - 按{sort_label}"

    lines = [
        "---",
        "tags: [GitHub, Topic]",
        f'title: "{title}"',
        f"topic: {json.dumps(topic, ensure_ascii=False)}",
        f"sort: {sort}",
        f"limit: {limit}",
        f"count: {len(items)}",
        f"translate: {str(translate).lower()}",
        f"createTime: {datetime.now().isoformat(timespec='seconds')}",
        "status: 已采集",
        "---",
        "",
        f"# {title}",
        "",
        f"> **采集时间**: {now} | **Topic**: `{topic}` | **排序**: {sort_label} | **数量**: {len(items)}"
        + (" | **含中文翻译**" if translate else ""),
        "",
    ]

    if not items:
        lines.append("> [!warning] 未获取到 Topic 仓库数据")
        lines.append(">")
        lines.append("> 可能原因: topic 拼写错误、GitHub API 限流 (未认证 60次/小时) 或网络问题。")
        return "\n".join(lines) + "\n"

    # 表格表头
    if translate:
        lines.append("| # | 仓库 | Stars | Forks | 语言 | 描述 | 中文翻译 |")
        lines.append("|---|------|-------|-------|------|------|----------|")
    else:
        lines.append("| # | 仓库 | Stars | Forks | 语言 | 描述 |")
        lines.append("|---|------|-------|-------|------|------|")

    for item in items:
        rank = item.get("rank", "")
        repo = (item.get("repo") or "").replace("|", "\\|")
        stars = fmt_num(item.get("stars", 0))
        forks = fmt_num(item.get("forks", 0))
        lang = (item.get("language") or "N/A").replace("|", "\\|")
        desc = (item.get("description") or "").replace("|", "\\|").replace("\n", " ")
        # 仓库链接 (优先用 url 字段, 否则拼默认)
        url = item.get("url") or (f"https://github.com/{repo}" if repo else "")
        repo_link = f"[{repo}]({url})" if repo else ""
        row = f"| {rank} | {repo_link} | {stars} | {forks} | {lang} | {desc} |"
        if translate:
            desc_zh = (item.get("description_zh") or "").replace("|", "\\|").replace("\n", " ")
            row += f" {desc_zh} |"
        lines.append(row)

    lines.append("")
    lines.append("---")
    source = "opencli github topic (GitHub Search API)"
    if translate:
        source += " + deep-translator (Google 翻译)"
    lines.append(f"> 数据来源: {source} | 采集时间: {now}")
    return "\n".join(lines) + "\n"


def write_markdown(topic, sort, md_content):
    """保存 markdown, 返回路径

    文件名: topic_{topic}_{sort}_{日期}.md
    同名已存在则覆盖 (同日同筛选再跑视为刷新)
    """
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    topic_part = sanitize_filename(topic) or "untitled"
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"topic_{topic_part}_{sort}_{date_str}.md"
    md_path = OUTPUT_ROOT / filename
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def main():
    log("=" * 60)
    log("GitHub Topic 采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取参数: 命令行优先, 无则弹窗
    if len(sys.argv) >= 2:
        topic, sort, limit, translate = parse_args()
    else:
        topic, sort, limit, translate = show_input_dialog()

    if topic is None:
        # 用户取消弹窗
        log("用户取消, 退出")
        return 0

    log(f"参数: topic={topic}, sort={sort}, limit={limit}, translate={translate}")

    # 2. 检查 opencli 可用
    ok, _, err = run_opencli(["--version"], 10)
    if not ok:
        log(f"opencli 不可用: {err}")
        log("安装: npm install -g @jackwener/opencli")
        return 1

    # 3. 调用 topic (public API, 无需浏览器, 通常 1-3 秒)
    log(f"调用 github topic 中 (public API, 通常 1-3 秒)...")
    items = call_topic(topic, sort, limit)

    if items is None:
        log("调用失败, 退出")
        return 2

    log(f"获取到 {len(items)} 条结果")

    # 4. 翻译描述列 (可选)
    if translate and items:
        log("开始翻译描述列 (调用 deep-translator Google)...")
        translate_descriptions(items)
    elif translate:
        log("无结果, 跳过翻译")

    # 5. 生成 markdown
    md_content = build_markdown(topic, sort, limit, items, translate=translate)
    md_path = write_markdown(topic, sort, md_content)
    log(f"已保存: {md_path}")
    log("完成")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
