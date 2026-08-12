# -*- coding: utf-8 -*-
"""B站每周必看视频采集

调用 opencli bilibili weekly 命令, 获取指定期数的"每周必看"视频列表,
保存为 Obsidian Markdown 表格。

对应 CLI: d:/voice/opencli-main/src/clis/bilibili/weekly.ts
- 策略: COOKIE (需浏览器桥接, series/one 接口有风控 -352)
- 参数: number (期数, 留空=最新一期), limit (默认 30)
- 输出列: rank, title, author, play, like, coin, url

用法:
    python bilibili_weekly.py                       # 弹窗输入 (期数/数量)
    python bilibili_weekly.py                       # 默认: 最新一期/30 条
    python bilibili_weekly.py 200                   # 指定第 200 期
    python bilibili_weekly.py latest 50             # 最新一期, 取 50 条 (推荐)
    python bilibili_weekly.py "" 50                 # PowerShell 会吞掉空串, 请用 latest
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

# ============ 配置 ============
OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "B站" / "每周必看"
# COOKIE 策略需启动浏览器, 调用 series/list + series/one 两个接口
TIMEOUT_WEEKLY = 60


def show_input_dialog():
    """tkinter 弹窗: 期数 / 数量"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return None, None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    number_str = simpledialog.askstring(
        "B站每周必看",
        "期数 (留空=最新一期, 例如 200):",
        initialvalue="",
        parent=root,
    )
    if number_str is None:
        root.destroy()
        return None, None
    number = number_str.strip()

    limit_str = simpledialog.askstring(
        "数量",
        "获取前几条? (1-100):",
        initialvalue="30",
        parent=root,
    )
    root.destroy()
    try:
        limit = max(1, min(100, int(limit_str)))
    except (TypeError, ValueError):
        limit = 30

    return number, limit


def parse_args():
    """命令行参数解析: number limit

    位置参数:
      number: 期数 (留空字符串、"latest" 或 "l" 表示最新一期, 默认 "")
      limit:  数量, 默认 30

    注: PowerShell 会吞掉空串参数, 用 "latest" 关键字更可靠。
    """
    number = ""
    limit = 30

    args = sys.argv[1:]
    if len(args) >= 1:
        num_raw = args[0].strip()
        # latest / l / 空串 都视为最新一期
        if num_raw.lower() in ("latest", "l", ""):
            number = ""
        else:
            number = num_raw
    if len(args) >= 2:
        try:
            limit = max(1, min(100, int(args[1])))
        except ValueError:
            pass
    return number, limit


def call_weekly(number, limit):
    """调用 opencli bilibili weekly, 返回 list[dict] 或 None

    返回字段: rank, title, author, play, like, coin, url
    """
    # number 为空时传空串, CLI 内部会调用 series/list 解析最新期数
    args = [
        "bilibili", "weekly",
        number,  # 留空则 CLI 取最新
        "--limit", str(limit),
        "-f", "json",
    ]

    ok, stdout, err = run_opencli(args, TIMEOUT_WEEKLY)
    if not ok:
        log(f"weekly 调用失败: {err}")
        return None

    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        log(f"weekly 返回非数组: {type(data).__name__}")
        return []
    except json.JSONDecodeError as e:
        log(f"weekly JSON 解析失败: {e}")
        log(f"原始 stdout 前 300 字符: {stdout[:300] if stdout else '(空)'}")
        return None


def fmt_num(n):
    """12345 -> 1.2万, 100000000 -> 1.0亿"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n) if n else "0"
    if n >= 100_000_000:
        return f"{n/100_000_000:.1f}亿"
    if n >= 10_000:
        return f"{n/10_000:.1f}万"
    return str(n)


def build_markdown(number, limit, items):
    """生成 markdown 内容

    items: [{rank, title, author, play, like, coin, url}, ...]
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 实际期数从首条数据无法直接得到 (CLI 内部解析), 这里用参数显示
    number_label = f"第 {number} 期" if number else "最新一期"
    title = f"B站每周必看 - {number_label}"

    lines = [
        "---",
        "tags: [B站, 每周必看]",
        f'title: "{title}"',
        f"number: {json.dumps(number, ensure_ascii=False)}",
        f"limit: {limit}",
        f"count: {len(items)}",
        f"createTime: {datetime.now().isoformat(timespec='seconds')}",
        "status: 已采集",
        "---",
        "",
        f"# {title}",
        "",
        f"> **采集时间**: {now} | **期数**: {number_label} | **数量**: {len(items)}",
        "",
    ]

    if not items:
        lines.append("> [!warning] 未获取到每周必看数据")
        lines.append(">")
        lines.append("> 可能原因: 浏览器未登录 B站、cookie 过期、或风控触发 (-352)。")
        return "\n".join(lines) + "\n"

    # 表格
    lines.append("| # | 标题 | UP主 | 播放 | 点赞 | 投币 |")
    lines.append("|---|------|------|------|------|------|")
    for item in items:
        rank = item.get("rank", "")
        title_text = (item.get("title") or "").replace("|", "\\|").replace("\n", " ")
        author = (item.get("author") or "").replace("|", "\\|")
        play = fmt_num(item.get("play", 0))
        like = fmt_num(item.get("like", 0))
        coin = fmt_num(item.get("coin", 0))
        url = item.get("url") or ""
        # 标题带视频链接
        title_link = f"[{title_text}]({url})" if url and title_text else title_text
        lines.append(f"| {rank} | {title_link} | {author} | {play} | {like} | {coin} |")

    lines.append("")
    lines.append("---")
    lines.append(f"> 数据来源: opencli bilibili weekly | 采集时间: {now}")
    return "\n".join(lines) + "\n"


def write_markdown(number, md_content):
    """保存 markdown, 返回路径

    文件名: weekly_{期数或latest}_{日期}.md
    """
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    number_part = sanitize_filename(number) if number else "latest"
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"weekly_{number_part}_{date_str}.md"
    md_path = OUTPUT_ROOT / filename
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def main():
    log("=" * 60)
    log("B站每周必看 采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取参数: 命令行优先, 无则弹窗
    if len(sys.argv) >= 2:
        number, limit = parse_args()
    else:
        number, limit = show_input_dialog()

    if number is None:
        # 用户取消弹窗
        log("用户取消, 退出")
        return 0

    number_label = number or "最新一期"
    log(f"参数: number={number_label}, limit={limit}")

    # 2. 检查 opencli 可用
    ok, _, err = run_opencli(["--version"], 10)
    if not ok:
        log(f"opencli 不可用: {err}")
        log("安装: npm install -g @jackwener/opencli")
        return 1

    # 3. 调用 weekly (COOKIE 策略, 需启动浏览器, 约 10-30 秒)
    log("调用 bilibili weekly 中 (COOKIE 策略, 约 10-30 秒)...")
    items = call_weekly(number, limit)

    if items is None:
        log("调用失败, 退出")
        return 2

    log(f"获取到 {len(items)} 条结果")

    # 4. 生成 markdown
    md_content = build_markdown(number, limit, items)
    md_path = write_markdown(number, md_content)
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
