# -*- coding: utf-8 -*-
"""B站关注博主的近期视频采集 (静态展示, 手动刷新)

依赖 bilibili_following.py 产出的 following_cache.json (mid + name 列表)。
若缓存不存在或过期, 会自动调用 bilibili following 拉取一次。

输出: 关注视频.md, 每个博主一个 callout, 内含近期视频列表。

用法:
    python bilibili_videos.py                 # 默认每人 3 条视频
    python bilibili_videos.py --videos 5      # 每人 5 条
    python bilibili_videos.py --refresh       # 先刷新关注列表缓存
"""

import json
import sys
import time
import random
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OPENCLI_CMD,
    OUTPUT_ROOT,
    log,
    run_opencli,
)

OUTPUT_DIR = OUTPUT_ROOT.parent / "B站关注"
CACHE_FILE = OUTPUT_DIR / "following_cache.json"
MD_FILE = OUTPUT_DIR / "关注视频.md"
WEEKLY_MD_FILE = OUTPUT_DIR / "本周视频.md"
MONTHLY_MD_FILE = OUTPUT_DIR / "本月视频.md"
TIMEOUT_VIDEOS = 30


def load_following_cache():
    """读取关注列表缓存, 返回 list[{mid, name, sign, fans}]"""
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log(f"缓存 JSON 解析失败: {e}")
        return None


def refresh_following_cache(limit=50):
    """调用 bilibili_following.py 重新生成缓存"""
    import subprocess
    script = Path(__file__).parent / "bilibili_following.py"
    log(f"刷新关注列表缓存: python {script} --limit {limit}")
    result = subprocess.run(
        [sys.executable, str(script), "--limit", str(limit)],
        cwd=str(OUTPUT_ROOT.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        log(f"刷新缓存失败: {result.stderr[:200] if result.stderr else 'unknown'}")
        return False
    return CACHE_FILE.exists()


def fetch_user_videos(mid, limit=3):
    """获取用户近几条投稿视频

    返回: list[dict] (rank, title, plays, likes, date, url)
    """
    ok, stdout, err = run_opencli(
        ["bilibili", "user-videos", str(mid), "--limit", str(limit), "-f", "json"],
        TIMEOUT_VIDEOS,
    )
    if not ok:
        log(f"  user-videos 调用失败 (mid={mid}): {err[:80] if err else ''}")
        return []
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError as e:
        log(f"  user-videos JSON 解析失败: {e}")
    return []


def fmt_num(n):
    """12345 -> 1.2万"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n) if n else "0"
    if n >= 10000:
        return f"{n/10000:.1f}万"
    return str(n)


def collect_all_videos(users, videos_per_user=3):
    """收集所有博主的视频数据

    Args:
        users: list[{mid, name, ...}] 关注列表
        videos_per_user: int 每个博主拉取的视频数

    Returns:
        list[{user_name, videos}] 每个博主的视频数据列表
        int: 成功拉取的博主数
        int: 失败的博主数
    """
    all_videos = []
    ok_count = 0
    fail_count = 0

    for i, u in enumerate(users, 1):
        mid = u.get("mid") or ""
        name = (u.get("name") or "").strip()

        log(f"[{i}/{len(users)}] {name} (mid={mid})")

        # 拉取视频
        videos = fetch_user_videos(mid, limit=videos_per_user) if mid else []

        if videos:
            ok_count += 1
            all_videos.append({
                "user_name": name,
                "videos": videos
            })
        else:
            fail_count += 1
            all_videos.append({
                "user_name": name,
                "videos": []
            })

        # 风控间隔
        if i < len(users):
            time.sleep(random.uniform(1, 2))

    return all_videos, ok_count, fail_count


def build_markdown(all_videos, videos_per_user=3, ok_count=0, fail_count=0):
    """生成视频汇总 markdown: 每博主一个 callout

    Args:
        all_videos: list[{user_name, videos}] 已收集的视频数据
        videos_per_user: int 每个博主拉取的视频数 (用于显示)
        ok_count: int 成功拉取的博主数
        fail_count: int 失败的博主数

    Returns:
        str markdown 内容
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "---",
        "tags: [B站, 关注视频]",
        f"更新时间: {now}",
        f"博主数: {len(all_videos)}",
        f"视频条数: {videos_per_user}",
        "---",
        "",
        "# B站关注视频",
        "",
        f"> **最近更新**: {now} | **共 {len(all_videos)} 位博主** | **每人近 {videos_per_user} 条视频**",
        "",
    ]

    for i, entry in enumerate(all_videos, 1):
        user_name = entry.get("user_name", "")
        videos = entry.get("videos", [])

        # callout 头
        lines.append(f"> [!note] {i}. {user_name}")
        lines.append(">")

        if videos:
            for v in videos:
                v_title = (v.get("title") or "").replace("|", "\\|").strip()
                v_plays = fmt_num(v.get("plays", 0))
                v_date = v.get("date") or ""
                v_url = v.get("url") or ""
                # 链接显示文字: 发布日期+标题 拼接 (日期为空时只显示标题)
                link_text = f"{v_date} {v_title}".strip() if v_date else v_title
                lines.append(f"> - [{link_text}]({v_url}) | 播放 {v_plays}")
        else:
            lines.append("> _暂无视频数据_")
        lines.append("")

    lines.append("---")
    lines.append(f"> 数据来源: opencli bilibili user-videos | 采集时间: {now} | 成功 {ok_count} / 失败 {fail_count}")
    return "\n".join(lines) + "\n"


def parse_video_date(date_str):
    """解析视频日期字符串, 返回 datetime 对象"""
    if not date_str:
        return None
    try:
        # 支持 YYYY-MM-DD 格式
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def filter_videos_by_days(all_videos, days):
    """筛选指定天数内的视频

    Args:
        all_videos: list[{user_name, videos}] 每个博主的视频列表
        days: int 天数阈值 (7=本周, 30=本月)

    Returns:
        list[{user_name, videos}] 筛选后的视频列表 (仅包含有符合时间视频的博主)
    """
    now = datetime.now()
    threshold = now - __import__('datetime').timedelta(days=days)

    filtered = []
    for entry in all_videos:
        user_name = entry.get("user_name", "")
        videos = entry.get("videos", [])
        time_matched = []

        for v in videos:
            v_date = parse_video_date(v.get("date", ""))
            if v_date and v_date >= threshold:
                time_matched.append(v)

        if time_matched:
            filtered.append({
                "user_name": user_name,
                "videos": time_matched
            })

    return filtered


def build_time_based_markdown(filtered_videos, time_label, time_range):
    """生成按时间筛选的视频 markdown

    Args:
        filtered_videos: list[{user_name, videos}] 筛选后的视频数据
        time_label: str 时间标签 (如 "本周", "本月")
        time_range: str 时间范围描述 (如 "7天内", "30天内")

    Returns:
        str markdown 内容
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_videos = sum(len(e.get("videos", [])) for e in filtered_videos)
    total_users = len(filtered_videos)

    lines = [
        "---",
        f"tags: [B站, {time_label}视频]",
        f"更新时间: {now}",
        f"博主数: {total_users}",
        f"视频条数: {total_videos}",
        "---",
        "",
        f"# B站关注博主{time_label}视频",
        "",
        f"> **最近更新**: {now} | **共 {total_users} 位博主有{time_range}新视频** | **{total_videos} 条视频**",
        "",
    ]

    for i, entry in enumerate(filtered_videos, 1):
        user_name = entry.get("user_name", "")
        videos = entry.get("videos", [])

        lines.append(f"> [!note] {i}. {user_name}")
        lines.append(">")

        for v in videos:
            v_title = (v.get("title") or "").replace("|", "\\|").strip()
            v_plays = fmt_num(v.get("plays", 0))
            v_date = v.get("date") or ""
            v_url = v.get("url") or ""
            link_text = f"{v_date} {v_title}".strip() if v_date else v_title
            lines.append(f"> - [{link_text}]({v_url}) | 播放 {v_plays}")

        lines.append("")

    lines.append("---")
    lines.append(f"> 数据来源: opencli bilibili user-videos | 采集时间: {now} | 筛选: {time_range}")
    return "\n".join(lines) + "\n"


def main():
    log("=" * 60)
    log("B站关注视频采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出文件: {MD_FILE}, {WEEKLY_MD_FILE}, {MONTHLY_MD_FILE}")
    log("=" * 60)

    # 参数
    videos_per_user = 3
    refresh = False
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--videos" and i + 1 < len(args):
            try:
                videos_per_user = int(args[i + 1])
            except ValueError:
                pass
        elif arg == "--refresh":
            refresh = True

    log(f"每人视频数: {videos_per_user}, 强制刷新缓存: {refresh}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 读取/刷新缓存
    users = None if refresh else load_following_cache()
    if not users:
        log("缓存不存在或需刷新, 调用 bilibili_following.py 生成缓存...")
        if not refresh_following_cache(limit=50):
            log("无法获取关注列表缓存, 终止")
            return 2
        users = load_following_cache()
        if not users:
            log("缓存仍为空, 终止")
            return 2

    log(f"关注博主数: {len(users)}, 开始拉取视频...")

    # 2. 收集所有视频数据
    all_videos, ok_count, fail_count = collect_all_videos(users, videos_per_user)

    # 3. 生成关注视频.md
    md_content = build_markdown(all_videos, videos_per_user, ok_count, fail_count)
    MD_FILE.write_text(md_content, encoding="utf-8")
    log(f"已保存: {MD_FILE}")

    # 4. 生成本周视频.md (7天内)
    weekly_videos = filter_videos_by_days(all_videos, 7)
    if weekly_videos:
        weekly_md = build_time_based_markdown(weekly_videos, "本周", "7天内")
        WEEKLY_MD_FILE.write_text(weekly_md, encoding="utf-8")
        log(f"已保存: {WEEKLY_MD_FILE} ({len(weekly_videos)} 位博主有本周新视频)")
    else:
        log("本周无新视频, 跳过生成")

    # 5. 生成本月视频.md (30天内)
    monthly_videos = filter_videos_by_days(all_videos, 30)
    if monthly_videos:
        monthly_md = build_time_based_markdown(monthly_videos, "本月", "30天内")
        MONTHLY_MD_FILE.write_text(monthly_md, encoding="utf-8")
        log(f"已保存: {MONTHLY_MD_FILE} ({len(monthly_videos)} 位博主有本月新视频)")
    else:
        log("本月无新视频, 跳过生成")

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
