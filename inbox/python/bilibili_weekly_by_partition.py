# -*- coding: utf-8 -*-
"""B站每周必看 按分区追加笔记

调用 opencli bilibili weekly 获取视频, 按 tname (分区) 分类,
将每期视频追加到对应分区笔记中 (每期一个段落, 含二级标题 + 视频表格)。

输出: d:/obsidian/demo/05_long_project/B站/每周必看/分区/{分区名}.md
首次创建时写入 frontmatter, 后续调用追加段落。

用法:
    python bilibili_weekly_by_partition.py              # 弹窗输入 (期数)
    python bilibili_weekly_by_partition.py latest       # 最新一期 (推荐)
    python bilibili_weekly_by_partition.py 200          # 指定第 200 期
    python bilibili_weekly_by_partition.py 200 --force  # 强制重新追加 (已存在仍追加)
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OBSIDIAN_ROOT,
    log,
    sanitize_filename,
)
from bilibili_weekly import call_weekly, fetch_episode_name, fmt_num  # noqa: E402

OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "B站" / "每周必看" / "分区"


def get_processed_episodes():
    """扫描分区目录所有 md 文件, 返回已处理的期数集合

    通过解析 "## 第 N 期" 二级标题提取期数 (N 为整数)。
    任意分区文件包含该期数即视为已处理。

    返回: set[int] 已处理的期数集合
    """
    if not OUTPUT_ROOT.exists():
        return set()
    processed = set()
    for md_path in OUTPUT_ROOT.glob("*.md"):
        try:
            content = md_path.read_text(encoding="utf-8")
            # 匹配 "## 第 385 期" (期数为数字)
            for m in re.finditer(r"^##\s+第\s+(\d+)\s+期", content, re.MULTILINE):
                try:
                    processed.add(int(m.group(1)))
                except ValueError:
                    pass
        except Exception as e:
            log(f"  扫描 {md_path.name} 失败: {str(e)[:60]}")
    return processed


def show_input_dialog():
    """tkinter 弹窗: 期数"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    number_str = simpledialog.askstring(
        "B站每周必看 按分区",
        "期数 (留空=最新一期, 例如 200 或 latest):",
        initialvalue="latest",
        parent=root,
    )
    root.destroy()
    if number_str is None:
        return None
    num = number_str.strip()
    if num.lower() in ("latest", "l", ""):
        return ""
    return num


def parse_args():
    """命令行参数: number"""
    args = sys.argv[1:]
    if not args:
        return ""
    num = args[0].strip()
    if num.lower() in ("latest", "l", ""):
        return ""
    return num


def build_section_header(number, episode_name, count):
    """生成追加段落的二级标题

    返回: "## 第 385 期 (2026-07-31 ~ 2026-08-06) - 2 条"

    number 为空时, 自动从 episode_name 提取实际期数。
    """
    import re as _re
    # 解析实际期数
    actual_number = number
    if not number and episode_name:
        m = _re.search(r"第(\d+)期", episode_name)
        if m:
            actual_number = m.group(1)
    number_str = actual_number or "最新"
    # 从 episode_name 解析日期范围
    from bilibili_weekly import parse_episode_info
    ep_info = parse_episode_info(episode_name) if episode_name else None
    if ep_info:
        date_range = f"{ep_info['date_start']} ~ {ep_info['date_end']}"
        return f"## 第 {number_str} 期 ({date_range}) - {count} 条"
    return f"## 第 {number_str} 期 - {count} 条"


def build_partition_table(items):
    """生成分区视频表格 (精简列)

    items: 同分区视频列表
    返回: markdown 表格字符串
    """
    lines = [
        "| # | 标题 | UP主 | 时长 | 发布 | 播放 | 点赞 | 投币 |",
        "|---|------|------|------|------|------|------|------|",
    ]
    for i, item in enumerate(items, 1):
        title_text = (item.get("title") or "").replace("|", "\\|").replace("\n", " ")
        author = (item.get("author") or "").replace("|", "\\|")
        duration = item.get("duration") or ""
        pubdate = item.get("pubdate") or ""
        play = fmt_num(item.get("play", 0))
        like = fmt_num(item.get("like", 0))
        coin = fmt_num(item.get("coin", 0))
        url = item.get("url") or ""
        title_link = f"[{title_text}]({url})" if url and title_text else title_text
        lines.append(
            f"| {i} | {title_link} | {author} | {duration} | {pubdate} | "
            f"{play} | {like} | {coin} |"
        )
    return "\n".join(lines)


def append_to_partition_file(tname, section_md):
    """追加段落到分区笔记

    tname: 分区名 (如 "鬼畜调教")
    section_md: 要追加的段落内容 (二级标题 + 表格)
    """
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    # 文件名: 用 sanitize 处理分区名
    safe_name = sanitize_filename(tname) or "未知分区"
    md_path = OUTPUT_ROOT / f"{safe_name}.md"

    if not md_path.exists():
        # 首次创建: 写入 frontmatter + 一级标题
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = [
            "---",
            "tags: [B站, 每周必看, 分区]",
            f'title: "B站每周必看 - {tname}"',
            f"partition: {json.dumps(tname, ensure_ascii=False)}",
            f"createTime: {datetime.now().isoformat(timespec='seconds')}",
            "status: 持续追加",
            "---",
            "",
            f"# B站每周必看 - {tname}",
            "",
            f"> 分区笔记, 每期视频自动追加。最后更新: {now}",
            "",
        ]
        content = "\n".join(header) + "\n" + section_md + "\n"
    else:
        # 已存在: 追加到文件末尾
        existing = md_path.read_text(encoding="utf-8").rstrip()
        content = existing + "\n\n" + section_md + "\n"

    md_path.write_text(content, encoding="utf-8")
    return md_path


def process_episode_by_partition(items, number, episode_name):
    """将一期视频按分区追加到对应笔记

    items: list[dict] weekly 返回的视频列表
    number: str 期数 (空串=最新)
    episode_name: str series/list 的 name (如 "2026第385期 07.31 - 08.06")

    返回: int 影响的分区数
    """
    # 按 tname 分组
    partitions = {}  # {tname: [items]}
    no_partition = []
    for item in items:
        tname = (item.get("tname") or "").strip()
        if tname:
            partitions.setdefault(tname, []).append(item)
        else:
            no_partition.append(item)

    if no_partition:
        partitions["未知分区"] = no_partition

    log(f"分区数: {len(partitions)}")
    for tname, vids in partitions.items():
        log(f"  - {tname}: {len(vids)} 条")

    # 逐分区追加
    log("追加到分区笔记...")
    for tname, vids in partitions.items():
        # 每分区单独生成段落标题 (count 为该分区视频数)
        section_header = build_section_header(number, episode_name, len(vids))
        section_md = section_header + "\n\n" + build_partition_table(vids)
        md_path = append_to_partition_file(tname, section_md)
        log(f"  {tname}: +{len(vids)} 条 → {md_path.name}")

    return len(partitions)


def main():
    log("=" * 60)
    log("B站每周必看 按分区追加笔记 启动")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 参数 (--force 强制重新追加)
    force = "--force" in sys.argv
    if force:
        sys.argv = [a for a in sys.argv if a != "--force"]

    if len(sys.argv) >= 2:
        number = parse_args()
    else:
        number = show_input_dialog()

    if number is None:
        log("用户取消, 退出")
        return 0

    number_label = number or "最新一期"
    log(f"参数: number={number_label}, force={force}")

    # 2. 调用 weekly
    log("调用 bilibili weekly (COOKIE 策略, 约 8-15 秒)...")
    items = call_weekly(number, 100)  # 取全部 (每期通常 30 条)

    if items is None:
        log("调用失败, 退出")
        return 2

    if not items:
        log("无数据, 退出")
        return 2

    log(f"获取到 {len(items)} 条视频")

    # 3. 获取期数 name (用于段落标题 + 去重判断)
    log("获取期数信息...")
    episode_name = fetch_episode_name(number)
    if episode_name:
        log(f"期数名称: {episode_name}")

    # 3.5 去重检查: 解析实际期数, 若已处理则跳过 (除非 --force)
    actual_num = None
    if number:
        try:
            actual_num = int(number)
        except ValueError:
            pass
    elif episode_name:
        m = re.search(r"第(\d+)期", episode_name)
        if m:
            actual_num = int(m.group(1))

    if actual_num is not None and not force:
        processed = get_processed_episodes()
        if actual_num in processed:
            log(f"⚠ 第 {actual_num} 期已存在于分区笔记中, 跳过")
            log(f"  (使用 --force 强制重新追加: python bilibili_weekly_by_partition.py {actual_num} --force)")
            return 0

    # 4. 按分区追加
    log("-" * 60)
    partition_count = process_episode_by_partition(items, number, episode_name)

    log("-" * 60)
    log(f"完成: 共 {partition_count} 个分区, {len(items)} 条视频")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
