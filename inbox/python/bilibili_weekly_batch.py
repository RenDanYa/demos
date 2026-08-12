# -*- coding: utf-8 -*-
"""B站每周必看 批量采集 (按年份)

调用 B站 series/list 公开 API 获取期数列表, 筛选指定年份, 循环调用
bilibili_weekly.call_weekly 为每一期生成 markdown 文件。

用法:
    python bilibili_weekly_batch.py                # 弹窗输入 (年份/数量限制)
    python bilibili_weekly_batch.py 2026           # 生成 2026 年全部期数 (失败的可重试)
    python bilibili_weekly_batch.py 2026 --limit 3 # 仅最新 3 期 (测试)
    python bilibili_weekly_batch.py 2026 --skip-failed  # 跳过所有已处理 (含失败)
    python bilibili_weekly_batch.py 2026 --force   # 强制全部重新追加 (含已成功)
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OBSIDIAN_ROOT,
    log,
)
from bilibili_weekly import call_weekly  # noqa: E402

# ============ 配置 ============
SERIES_LIST_URL = "https://api.bilibili.com/x/web-interface/popular/series/list"
TIMEOUT_SERIES_LIST = 15
OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "B站" / "每周必看"


def fetch_series_list():
    """调用 B站 series/list 公开 API, 返回期数列表

    返回: list[dict] (按 number 降序), 每项含 number/subject/name/status
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    r = requests.get(SERIES_LIST_URL, headers=headers, timeout=TIMEOUT_SERIES_LIST)
    data = r.json()
    if data.get("code") != 0:
        log(f"series/list 调用失败: code={data.get('code')}, msg={data.get('message')}")
        return []
    return data.get("data", {}).get("list", [])


def filter_by_year(series, year):
    """筛选指定年份的期数

    series: list[dict] (按 number 降序)
    year: int (如 2026)
    返回: list[dict] (按 number 升序, 即从早到晚)
    """
    year_prefix = str(year)
    matched = [ep for ep in series if ep.get("name", "").startswith(year_prefix)]
    # 按期数升序 (从早到晚)
    matched.sort(key=lambda x: x.get("number", 0))
    return matched


def parse_args():
    """命令行参数: year [--limit n]"""
    year = datetime.now().year
    limit = 0  # 0 = 不限制

    args = sys.argv[1:]
    if "--limit" in args:
        i = args.index("--limit")
        if i + 1 < len(args):
            try:
                limit = max(1, int(args[i + 1]))
            except ValueError:
                pass
            args = args[:i] + args[i + 2:]

    for a in args:
        if a and not a.startswith("-"):
            try:
                year = int(a)
            except ValueError:
                pass
            break

    return year, limit


def show_input_dialog():
    """tkinter 弹窗: 年份 / 数量限制"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return None, None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    year_str = simpledialog.askstring(
        "B站每周必看 批量",
        f"年份 (如 2026, 默认今年 {datetime.now().year}):",
        initialvalue=str(datetime.now().year),
        parent=root,
    )
    if year_str is None:
        root.destroy()
        return None, None
    try:
        year = int(year_str.strip())
    except ValueError:
        year = datetime.now().year

    limit_str = simpledialog.askstring(
        "数量限制",
        "生成最近几期? (留空=全部, 例如 3):",
        initialvalue="",
        parent=root,
    )
    root.destroy()
    try:
        limit = int((limit_str or "").strip()) if (limit_str or "").strip() else 0
    except ValueError:
        limit = 0

    return year, limit


def main():
    log("=" * 60)
    log("B站每周必看 批量采集 启动")
    log("=" * 60)

    # 1. 参数
    if len(sys.argv) >= 2:
        year, limit = parse_args()
    else:
        year, limit = show_input_dialog()

    if year is None:
        log("用户取消, 退出")
        return 0

    log(f"参数: year={year}, limit={limit or '全部'}")

    # 1.5 显示已处理统计 (按状态)
    try:
        from bilibili_weekly_by_partition import get_episode_stats
        stats = get_episode_stats()
        total_p = len(stats["success"]) + len(stats["empty"]) + len(stats["error"])
        if total_p > 0:
            log(
                f"已处理: {total_p} 期 "
                f"(成功 {len(stats['success'])}, 空 {len(stats['empty'])}, "
                f"错误 {len(stats['error'])})"
            )
    except Exception:
        pass

    # 2. 获取期数列表
    log("调用 series/list API 获取期数列表...")
    series = fetch_series_list()
    if not series:
        log("未获取到期数列表, 退出")
        return 1
    log(f"共 {len(series)} 期")

    # 3. 筛选指定年份
    episodes = filter_by_year(series, year)
    if not episodes:
        log(f"{year} 年未找到任何期数, 退出")
        return 2

    # 应用 limit: 取最新 N 期 (即列表末尾 N 项, 因为已按升序)
    total_year = len(episodes)
    if limit > 0 and limit < total_year:
        episodes = episodes[-limit:]
        log(f"{year} 年共 {total_year} 期, 限制为最新 {limit} 期")

    # 3.5 去重 (按状态区分)
    #    默认: 只跳过 success (失败的可重试)
    #    --skip-failed: 跳过所有 (含 empty/error)
    #    --force: 不跳过任何
    force = "--force" in sys.argv
    skip_failed = "--skip-failed" in sys.argv
    for flag in ("--force", "--skip-failed"):
        sys.argv = [a for a in sys.argv if a != flag]

    if force:
        log("⚠ --force 模式: 不跳过任何期数, 全部重新追加")
    else:
        try:
            from bilibili_weekly_by_partition import get_processed_episodes
            processed = get_processed_episodes(include_failed=skip_failed)
            if processed:
                before = len(episodes)
                episodes = [ep for ep in episodes if ep.get("number") not in processed]
                skipped = before - len(episodes)
                if skipped > 0:
                    mode = "所有已处理 (含失败)" if skip_failed else "已成功"
                    log(f"跳过{mode}期数: {skipped} 期")
                    if not episodes:
                        log("全部期数已处理, 无需重复, 退出")
                        return 0
        except Exception as e:
            log(f"⚠ 去重检查失败 (继续全量): {str(e)[:80]}")

    total = len(episodes)
    log(f"待生成: {total} 期 (第 {episodes[0]['number']}-{episodes[-1]['number']} 期)")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("预计耗时: 每期约 8-15 秒 (COOKIE 策略)")
    log("-" * 60)

    # 4. 循环调用 weekly, 按分区追加到笔记
    from bilibili_weekly_by_partition import (
        process_episode_by_partition,
        record_failed,
    )
    success_count = 0
    empty_count = 0
    error_count = 0
    start_time = time.time()

    for i, ep in enumerate(episodes, 1):
        number = str(ep.get("number", ""))
        subject = ep.get("subject", "")
        name = ep.get("name", "")
        log(f"[{i}/{total}] 第 {number} 期: {subject} ({name})")

        # 调用 weekly (limit 100, 取每期全部视频)
        items = call_weekly(number, 100)

        if items is None:
            log(f"  失败, 跳过 [error]")
            try:
                record_failed(int(number), status="error", reason="weekly 调用失败")
            except ValueError:
                pass
            error_count += 1
            time.sleep(2)
            continue

        if not items:
            log(f"  空数据, 跳过 [empty]")
            try:
                record_failed(int(number), status="empty", reason="API 返回空数组")
            except ValueError:
                pass
            empty_count += 1
            continue

        # 按分区追加到笔记 (内部自动记录 success)
        partition_count = process_episode_by_partition(items, number, name)
        log(f"  成功: {len(items)} 条 → {partition_count} 个分区 [success]")
        success_count += 1

        # 间隔避免风控
        if i < total:
            time.sleep(1)

    elapsed = time.time() - start_time
    log("-" * 60)
    log(f"批量完成: 成功 {success_count}, 空数据 {empty_count}, 错误 {error_count}")
    log(f"总耗时: {elapsed:.0f} 秒 ({elapsed/60:.1f} 分钟)")
    return 0 if (empty_count + error_count) == 0 else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
