# -*- coding: utf-8 -*-
"""B站每周必看 按分区追加笔记

调用 opencli bilibili weekly 获取视频, 按 tname (分区) 分类,
将每期视频追加到对应分区笔记的表格中 (期数作首列, 单一连续表格)。

输出:
- 分区笔记: d:/obsidian/demo/05_long_project/B站/每周必看/分区/{分区名}.md
- 处理日志: d:/obsidian/demo/05_long_project/B站/每周必看/分区/_processed.json
  记录已处理期数, 下次调用自动跳过。

用法:
    python bilibili_weekly_by_partition.py              # 弹窗输入 (期数)
    python bilibili_weekly_by_partition.py latest       # 最新一期 (推荐)
    python bilibili_weekly_by_partition.py 200          # 指定第 200 期 (失败的可自动重试)
    python bilibili_weekly_by_partition.py 200 --force  # 强制重新追加 (已成功也重做)
    python bilibili_weekly_batch.py 2026 --skip-failed  # 跳过所有已处理 (含失败)
    python bilibili_weekly_batch.py 2026                # 默认只跳过成功, 失败的重试
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
# 处理日志: 记录已处理期数, 避免重复读取
LOG_FILE = OUTPUT_ROOT / "_processed.json"


def load_processed_log():
    """读取处理日志, 返回 dict {期数: {time, partitions, count}}

    格式:
    {
      "385": {"time": "2026-08-12T21:00:52", "partitions": ["数码", "人文历史"], "count": 5},
      ...
    }
    """
    if not LOG_FILE.exists():
        return {}
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"⚠ 读取日志失败: {str(e)[:60]}, 视为空日志")
        return {}


def save_processed_log(log_data):
    """保存处理日志"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(
        json.dumps(log_data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def record_processed(number, partitions=None, count=0, status="success", reason=""):
    """记录一期处理结果到日志

    number: int 期数
    partitions: list[str] 影响的分区名列表 (成功时)
    count: int 视频总数
    status: str 状态 - "success" | "empty" | "error"
    reason: str 失败原因 (status != success 时)
    """
    log_data = load_processed_log()
    entry = {
        "status": status,
        "time": datetime.now().isoformat(timespec="seconds"),
        "partitions": partitions or [],
        "count": count,
    }
    if reason:
        entry["reason"] = reason
    log_data[str(number)] = entry
    save_processed_log(log_data)


def record_failed(number, status="empty", reason=""):
    """记录失败的期数 (便捷封装)

    number: int 期数
    status: "empty" (API 返回空) | "error" (调用失败)
    reason: str 失败原因
    """
    record_processed(number, status=status, reason=reason)


def get_episode_stats():
    """返回按状态分类的期数统计

    返回: dict {success: set, empty: set, error: set}
    旧日志无 status 字段时视为 success (向后兼容)。
    """
    stats = {"success": set(), "empty": set(), "error": set()}
    log_data = load_processed_log()
    if not log_data:
        return stats
    for k, v in log_data.items():
        try:
            num = int(k)
        except ValueError:
            continue
        if isinstance(v, dict):
            status = v.get("status", "success")
        else:
            status = "success"
        if status in stats:
            stats[status].add(num)
        else:
            stats["success"].add(num)
    return stats


def get_processed_episodes(include_failed=False):
    """返回已处理的期数集合

    include_failed=False: 只返回成功的 (默认, 失败的下次会重试)
    include_failed=True: 返回所有已处理 (成功+失败, 全部跳过)

    优先读取 _processed.json 日志; 若日志不存在或为空, 兜底扫描分区 md 文件。
    """
    # 1. 优先读日志
    stats = get_episode_stats()
    if stats["success"] or stats["empty"] or stats["error"]:
        if include_failed:
            return stats["success"] | stats["empty"] | stats["error"]
        return stats["success"]

    # 2. 兜底: 扫描 md 文件表格第4列期数 (无日志时)
    if not OUTPUT_ROOT.exists():
        return set()
    processed = set()
    for md_path in OUTPUT_ROOT.glob("*.md"):
        try:
            content = md_path.read_text(encoding="utf-8")
            for line in content.split("\n"):
                line = line.strip()
                if not line.startswith("|"):
                    continue
                cells = [c.strip() for c in line.split("|")]
                if len(cells) >= 5 and cells[4].isdigit():
                    try:
                        processed.add(int(cells[4]))
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


def build_table_header():
    """返回表格表头 + 分隔符 (期数倒序, 最新在顶部)"""
    return "| 年 | 月 | 周 | 期数 | 标题 | UP主 | 时长 | 发布 | 播放 | 点赞 | 投币 |\n|----|----|----|------|------|------|------|------|------|------|------|"


def build_table_rows(items, number_str, ep_info):
    """生成表格数据行

    items: 同分区视频列表
    number_str: 期数字符串 (如 "382")
    ep_info: dict {year, month, week, ...} 或 None
    返回: list[str] 数据行
    """
    year = ep_info.get("year", "") if ep_info else ""
    month = ep_info.get("month", "") if ep_info else ""
    week = ep_info.get("week", "") if ep_info else ""
    rows = []
    for item in items:
        title_text = (item.get("title") or "").replace("|", "\\|").replace("\n", " ")
        author = (item.get("author") or "").replace("|", "\\|")
        duration = item.get("duration") or ""
        pubdate = item.get("pubdate") or ""
        play = fmt_num(item.get("play", 0))
        like = fmt_num(item.get("like", 0))
        coin = fmt_num(item.get("coin", 0))
        url = item.get("url") or ""
        title_link = f"[{title_text}]({url})" if url and title_text else title_text
        rows.append(
            f"| {year} | {month} | {week} | {number_str} | {title_link} | {author} | "
            f"{duration} | {pubdate} | {play} | {like} | {coin} |"
        )
    return rows


def append_to_partition_file(tname, rows, number_str):
    """追加表格行到分区笔记 (倒序, 新期数插入表头后)

    tname: 分区名 (如 "鬼畜调教")
    rows: list[str] 表格数据行
    number_str: 期数字符串 (用于确定插入位置)

    首次创建: frontmatter + 标题 + 表头 + 数据行
    后续追加: 在表头分隔符后插入 (期数大的在前, 保持倒序)
    """
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(tname) or "未知分区"
    md_path = OUTPUT_ROOT / f"{safe_name}.md"

    if not md_path.exists():
        # 首次创建: frontmatter + 标题 + 表头 + 数据行
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = [
            "---",
            "tags: [B站, 每周必看, 分区]",
            f'title: "B站每周必看 - {tname}"',
            f"partition: {json.dumps(tname, ensure_ascii=False)}",
            f"createTime: {datetime.now().isoformat(timespec='seconds')}",
            f"updateTime: {datetime.now().isoformat(timespec='seconds')}",
            "status: 持续追加",
            "---",
            "",
            f"# B站每周必看 - {tname}",
            "",
            f"> 分区笔记, 按期数倒序排列 (最新在顶部)。最后更新: {now}",
            "",
            build_table_header(),
        ]
        content = "\n".join(header) + "\n" + "\n".join(rows) + "\n"
    else:
        # 后续追加: 找表头分隔符行, 在其后插入新行 (保持期数倒序)
        existing = md_path.read_text(encoding="utf-8")
        lines = existing.split("\n")
        # 找表头分隔符行 (|----|----|...)
        separator_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("|") and "---" in line and "期数" not in line:
                separator_idx = i
                break

        try:
            new_num = int(number_str) if number_str else 0
        except ValueError:
            new_num = 0

        if separator_idx >= 0:
            if new_num > 0:
                # 找插入位置: 跳过比新期数小的第一行前
                insert_idx = separator_idx + 1
                for i in range(separator_idx + 1, len(lines)):
                    line = lines[i].strip()
                    if not line.startswith("|"):
                        break
                    # 提取该行的期数 (第4列)
                    cells = [c.strip() for c in line.split("|")]
                    # cells[0] 为空, [1]=年 [2]=月 [3]=周 [4]=期数
                    if len(cells) >= 5:
                        try:
                            existing_num = int(cells[4])
                            if existing_num < new_num:
                                insert_idx = i
                                break
                            else:
                                insert_idx = i + 1
                        except ValueError:
                            insert_idx = i + 1
                            continue
                new_lines = lines[:insert_idx] + rows + lines[insert_idx:]
            else:
                # 期数未知, 追加到表头后
                new_lines = lines[:separator_idx + 1] + rows + lines[separator_idx + 1:]
        else:
            # 无表格 (异常), 追加表头 + 数据
            new_lines = lines + ["", build_table_header()] + rows
        content = "\n".join(new_lines)
        # 更新 updateTime
        now_iso = datetime.now().isoformat(timespec="seconds")
        content = re.sub(r"^updateTime:.*$", f"updateTime: {now_iso}", content, flags=re.MULTILINE)

    md_path.write_text(content, encoding="utf-8")
    return md_path


def process_episode_by_partition(items, number, episode_name):
    """将一期视频按分区追加到对应笔记

    items: list[dict] weekly 返回的视频列表
    number: str 期数 (空串=最新)
    episode_name: str series/list 的 name (如 "2026第385期 07.31 - 08.06")

    返回: int 影响的分区数
    """
    # 解析实际期数 + 年/月/周信息
    actual_number = number
    if not actual_number and episode_name:
        m = re.search(r"第(\d+)期", episode_name)
        if m:
            actual_number = m.group(1)
    number_str = actual_number or ""

    # 解析 ep_info (年/月/周)
    from bilibili_weekly import parse_episode_info
    ep_info = parse_episode_info(episode_name) if episode_name else None

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

    # 逐分区追加表格行 (倒序插入)
    log("追加到分区笔记...")
    for tname, vids in partitions.items():
        rows = build_table_rows(vids, number_str, ep_info)
        md_path = append_to_partition_file(tname, rows, number_str)
        log(f"  {tname}: +{len(vids)} 条 → {md_path.name}")

    # 记录到处理日志 (供下次去重)
    try:
        ep_num = int(number_str) if number_str else 0
        if ep_num > 0:
            record_processed(
                ep_num,
                partitions=list(partitions.keys()),
                count=len(items),
                status="success",
            )
            log(f"已记录到日志: 第 {ep_num} 期 [success] → {LOG_FILE.name}")
    except Exception as e:
        log(f"⚠ 记录日志失败: {str(e)[:60]}")

    return len(partitions)


def main():
    log("=" * 60)
    log("B站每周必看 按分区追加笔记 启动")
    log(f"输出目录: {OUTPUT_ROOT}")
    log(f"处理日志: {LOG_FILE}")
    # 打印已处理期数统计 (按状态分类)
    stats = get_episode_stats()
    total = len(stats["success"]) + len(stats["empty"]) + len(stats["error"])
    if total > 0:
        all_nums = stats["success"] | stats["empty"] | stats["error"]
        latest = max(all_nums)
        log(
            f"已处理: {total} 期 "
            f"(成功 {len(stats['success'])}, 空数据 {len(stats['empty'])}, "
            f"错误 {len(stats['error'])}) 最新: 第 {latest} 期"
        )
    else:
        log("已处理期数: 0 期")
    log("=" * 60)

    # 1. 参数解析
    force = "--force" in sys.argv
    skip_failed = "--skip-failed" in sys.argv
    for flag in ("--force", "--skip-failed"):
        sys.argv = [a for a in sys.argv if a != flag]

    if len(sys.argv) >= 2:
        number = parse_args()
    else:
        number = show_input_dialog()

    if number is None:
        log("用户取消, 退出")
        return 0

    number_label = number or "最新一期"
    flags = []
    if force:
        flags.append("force")
    if skip_failed:
        flags.append("skip-failed")
    flags_str = f", flags=[{','.join(flags)}]" if flags else ""
    log(f"参数: number={number_label}{flags_str}")

    # 2. 获取期数信息 (先获取, 用于去重判断 + 失败记录)
    log("获取期数信息...")
    episode_name = fetch_episode_name(number)
    if episode_name:
        log(f"期数名称: {episode_name}")

    # 3. 解析实际期数
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

    # 4. 去重检查 (按状态区分)
    #    默认: 只跳过 success (失败的可重试)
    #    --skip-failed: 也跳过 empty/error
    #    --force: 不跳过任何
    if actual_num is not None and not force:
        stats = get_episode_stats()
        if actual_num in stats["success"]:
            log(f"⚠ 第 {actual_num} 期已成功处理, 跳过")
            log(f"  (使用 --force 强制重新追加)")
            return 0
        if actual_num in (stats["empty"] | stats["error"]) and skip_failed:
            log(f"⚠ 第 {actual_num} 期已标记失败, --skip-failed 跳过")
            log(f"  (不加 --skip-failed 可重试该失败期数)")
            return 0

    # 5. 调用 weekly
    log("调用 bilibili weekly (COOKIE 策略, 约 8-15 秒)...")
    items = call_weekly(number, 100)  # 取全部 (每期通常 30 条)

    if items is None:
        if actual_num is not None:
            record_failed(actual_num, status="error", reason="weekly 调用失败")
            log(f"已记录到日志: 第 {actual_num} 期 [error]")
        log("调用失败, 退出")
        return 2

    if not items:
        if actual_num is not None:
            record_failed(actual_num, status="empty", reason="API 返回空数组")
            log(f"已记录到日志: 第 {actual_num} 期 [empty]")
        log("无数据 (B站 API 可能已下架该期数据), 退出")
        return 2

    log(f"获取到 {len(items)} 条视频")

    # 6. 按分区追加 (内部自动记录 success)
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
