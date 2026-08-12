# -*- coding: utf-8 -*-
"""GitHub Trending 仓库采集

调用 opencli github trending 命令, 抓取 github.com/trending 榜单,
保存为 Obsidian Markdown 表格。

对应 CLI: d:/voice/opencli-main/src/clis/github/trending.ts
- 策略: COOKIE (需浏览器桥接, 抓取服务端渲染的 HTML)
- 输出列: rank, repo, stars, stars_today, language, description

用法:
    python github_trending.py                              # 弹窗输入 (语言/区间/数量/翻译)
    python github_trending.py                              # 默认: 全语言/每日/25/翻译
    python github_trending.py python                       # 指定语言
    python github_trending.py python weekly 10              # 指定 语言/区间/数量
    python github_trending.py "" weekly 30                  # 留空=全语言
    python github_trending.py python daily 25 --no-translate  # 跳过翻译
"""

import json
import sys
import time
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

# ============ 配置 ============
OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "GitHub" / "Trending"
TIMEOUT_TRENDING = 90  # COOKIE 策略需启动浏览器, 加载 trending 页 + 2s settle, 给足冗余

VALID_SINCE = ("daily", "weekly", "monthly")

# ============ 翻译配置 ============
# deep-translator 的 GoogleTranslator 单次请求限制约 5000 字符, 用较小批次避免超限
TRANSLATE_BATCH_SIZE = 20
TRANSLATE_RETRY_MAX = 2  # 单条翻译失败重试次数
TRANSLATE_RETRY_WAIT = 2  # 重试间隔 (秒)


def translate_descriptions(items):
    """批量翻译描述列 (使用 deep-translator 的 Google 翻译)

    依赖: pip install deep-translator
    items: list[dict] (原地修改, 添加 description_zh 字段)
    失败时: description_zh 回退为原文, 不影响主流程
    """
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        log("翻译失败: 未安装 deep-translator, 请运行 pip install deep-translator")
        for item in items:
            item["description_zh"] = item.get("description", "")
        return

    translator = GoogleTranslator(source="en", target="zh-CN")

    # 收集非空描述及其索引
    pending = []  # [(index, description), ...]
    for i, item in enumerate(items):
        desc = (item.get("description") or "").strip()
        if desc:
            pending.append((i, desc))
        else:
            item["description_zh"] = ""

    if not pending:
        log("无待翻译描述, 跳过翻译")
        return

    log(f"待翻译描述: {len(pending)} 条, 分批调用 Google 翻译 (每批 {TRANSLATE_BATCH_SIZE} 条)...")

    total_batches = (len(pending) + TRANSLATE_BATCH_SIZE - 1) // TRANSLATE_BATCH_SIZE
    success_count = 0
    fail_count = 0

    for batch_start in range(0, len(pending), TRANSLATE_BATCH_SIZE):
        batch = pending[batch_start:batch_start + TRANSLATE_BATCH_SIZE]
        batch_num = batch_start // TRANSLATE_BATCH_SIZE + 1
        descs = [desc for _, desc in batch]

        log(f"  批次 {batch_num}/{total_batches}: 翻译 {len(batch)} 条...")

        translations = [None] * len(batch)
        all_ok = True

        for j, desc in enumerate(descs):
            translated = None
            for attempt in range(TRANSLATE_RETRY_MAX + 1):
                try:
                    translated = translator.translate(desc)
                    if translated:
                        break
                except Exception as e:
                    if attempt < TRANSLATE_RETRY_MAX:
                        log(f"    [{j+1}] 翻译失败, 重试 {attempt+1}/{TRANSLATE_RETRY_MAX}: {str(e)[:80]}")
                        time.sleep(TRANSLATE_RETRY_WAIT)
                    else:
                        log(f"    [{j+1}] 翻译最终失败: {str(e)[:80]}")

            if translated:
                translations[j] = translated
                success_count += 1
            else:
                translations[j] = desc  # 回退原文
                fail_count += 1
                all_ok = False

            # 短间隔, 避免触发 Google 限流
            if j < len(descs) - 1:
                time.sleep(0.3)

        # 回填翻译
        for (idx, _), translated in zip(batch, translations):
            items[idx]["description_zh"] = translated

        status = "完成" if all_ok else "部分失败(已回退原文)"
        log(f"  批次 {batch_num} {status}: {len(batch)} 条")

    log(f"翻译完成: 成功 {success_count}/{len(pending)}, 失败 {fail_count}")


def show_input_dialog():
    """tkinter 弹窗: 语言 / 区间 / 数量 / 翻译"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return None, None, None, None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    language = simpledialog.askstring(
        "GitHub Trending",
        "语言筛选 (留空=全语言, 例如 python/rust/go):",
        initialvalue="python",
        parent=root,
    )
    if language is None:
        root.destroy()
        return None, None, None, None
    language = language.strip()

    since = simpledialog.askstring(
        "时间区间",
        "时间区间 (daily/weekly/monthly):",
        initialvalue="daily",
        parent=root,
    )
    if since is None:
        root.destroy()
        return None, None, None, None
    since = since.strip().lower() or "daily"
    if since not in VALID_SINCE:
        since = "daily"

    limit_str = simpledialog.askstring(
        "数量",
        "获取前几条? (1-100):",
        initialvalue="25",
        parent=root,
    )
    if limit_str is None:
        root.destroy()
        return None, None, None, None
    try:
        limit = max(1, min(100, int(limit_str)))
    except (TypeError, ValueError):
        limit = 25

    # 翻译选项: 输入 n 跳过, 其他视为启用
    translate_str = simpledialog.askstring(
        "翻译描述",
        "是否翻译描述为中文? (y/n, 默认 y):",
        initialvalue="y",
        parent=root,
    )
    root.destroy()
    translate = (translate_str or "y").strip().lower() != "n"

    return language, since, limit, translate


def parse_args():
    """命令行参数解析: language since limit [--no-translate]"""
    language = ""
    since = "daily"
    limit = 25
    translate = True

    args = sys.argv[1:]
    # 提取 --no-translate 标志 (可出现在任意位置)
    if "--no-translate" in args:
        translate = False
        args = [a for a in args if a != "--no-translate"]

    if len(args) >= 1:
        language = args[0].strip()
    if len(args) >= 2:
        s = args[1].strip().lower()
        if s in VALID_SINCE:
            since = s
    if len(args) >= 3:
        try:
            limit = max(1, min(100, int(args[2])))
        except ValueError:
            pass
    return language, since, limit, translate


def call_trending(language, since, limit):
    """调用 opencli github trending, 返回 list[dict] 或空列表

    返回字段: rank, repo, stars, stars_today, language, description
    """
    args = ["github", "trending", "-f", "json", "--limit", str(limit), "--since", since]
    if language:
        args.extend(["--language", language])

    ok, stdout, err = run_opencli(args, TIMEOUT_TRENDING)
    if not ok:
        log(f"trending 调用失败: {err}")
        return None

    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        log(f"trending 返回非数组: {type(data).__name__}")
        return []
    except json.JSONDecodeError as e:
        log(f"trending JSON 解析失败: {e}")
        log(f"原始 stdout 前 300 字符: {stdout[:300] if stdout else '(空)'}")
        return None


def build_markdown(language, since, limit, items, translate=False):
    """生成 markdown 内容

    items: [{rank, repo, stars, stars_today, language, description, description_zh?}, ...]
    translate: 是否显示中文翻译列
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lang_label = language or "全语言"
    since_label = {"daily": "今日", "weekly": "本周", "monthly": "本月"}.get(since, since)
    title = f"GitHub Trending - {lang_label} - {since_label}"

    lines = [
        "---",
        "tags: [GitHub, Trending]",
        f'title: "{title}"',
        f"language: {json.dumps(language, ensure_ascii=False)}",
        f"since: {since}",
        f"limit: {limit}",
        f"count: {len(items)}",
        f"translate: {str(translate).lower()}",
        f"createTime: {datetime.now().isoformat(timespec='seconds')}",
        "status: 已采集",
        "---",
        "",
        f"# {title}",
        "",
        f"> **采集时间**: {now} | **语言**: {lang_label} | **区间**: {since_label} | **数量**: {len(items)}"
        + (" | **含中文翻译**" if translate else ""),
        "",
    ]

    if not items:
        lines.append("> [!warning] 未获取到 Trending 数据")
        lines.append(">")
        lines.append("> 可能原因: 浏览器未登录、cookie 过期、页面结构变更或该语言筛选无结果。")
        return "\n".join(lines) + "\n"

    # 表格表头
    if translate:
        lines.append("| # | 仓库 | Stars | 今日新增 | 语言 | 描述 | 中文翻译 |")
        lines.append("|---|------|-------|----------|------|------|----------|")
    else:
        lines.append("| # | 仓库 | Stars | 今日新增 | 语言 | 描述 |")
        lines.append("|---|------|-------|----------|------|------|")

    for item in items:
        rank = item.get("rank", "")
        repo = (item.get("repo") or "").replace("|", "\\|")
        stars = item.get("stars", "0")
        stars_today = item.get("stars_today", "") or ""
        lang = (item.get("language") or "N/A").replace("|", "\\|")
        desc = (item.get("description") or "").replace("|", "\\|").replace("\n", " ")
        # 仓库链接
        repo_link = f"[{repo}](https://github.com/{repo})" if repo else ""
        row = f"| {rank} | {repo_link} | {stars} | {stars_today} | {lang} | {desc} |"
        if translate:
            desc_zh = (item.get("description_zh") or "").replace("|", "\\|").replace("\n", " ")
            row += f" {desc_zh} |"
        lines.append(row)

    lines.append("")
    lines.append("---")
    source = "opencli github trending"
    if translate:
        source += " + deep-translator (Google 翻译)"
    lines.append(f"> 数据来源: {source} | 采集时间: {now}")
    return "\n".join(lines) + "\n"


def write_markdown(language, since, md_content):
    """保存 markdown, 返回路径

    文件名: trending_{语言}_{区间}_{日期}.md
    同名已存在则覆盖 (同日同筛选再跑视为刷新)
    """
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    lang_part = sanitize_filename(language) if language else "all"
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"trending_{lang_part}_{since}_{date_str}.md"
    md_path = OUTPUT_ROOT / filename
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def main():
    log("=" * 60)
    log("GitHub Trending 采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取参数: 命令行优先, 无则弹窗
    if len(sys.argv) >= 2:
        language, since, limit, translate = parse_args()
    else:
        language, since, limit, translate = show_input_dialog()

    if since is None:
        # 用户取消弹窗
        log("用户取消, 退出")
        return 0

    lang_label = language or "全语言"
    log(f"参数: language={lang_label}, since={since}, limit={limit}, translate={translate}")

    # 2. 检查 opencli 可用
    ok, _, err = run_opencli(["--version"], 10)
    if not ok:
        log(f"opencli 不可用: {err}")
        log("安装: npm install -g @jackwener/opencli")
        return 1

    # 3. 调用 trending
    log("调用 github trending 中, 请稍候 (约 10-30 秒, 需启动浏览器)...")
    items = call_trending(language, since, limit)

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
    md_content = build_markdown(language, since, limit, items, translate=translate)
    md_path = write_markdown(language, since, md_content)
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
