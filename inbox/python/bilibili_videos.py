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


def build_markdown(users, videos_per_user=3):
    """生成视频汇总 markdown: 每博主一个 callout"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "---",
        "tags: [B站, 关注视频]",
        f"更新时间: {now}",
        f"博主数: {len(users)}",
        f"视频条数: {videos_per_user}",
        "---",
        "",
        "# B站关注视频",
        "",
        f"> **最近更新**: {now} | **共 {len(users)} 位博主** | **每人近 {videos_per_user} 条视频**",
        "",
    ]

    ok_count = 0
    fail_count = 0

    for i, u in enumerate(users, 1):
        mid = u.get("mid") or ""
        name = (u.get("name") or "").strip()
        sign = (u.get("sign") or "").replace("\n", " ").replace("\r", " ").strip()
        fans = u.get("fans") or ""

        log(f"[{i}/{len(users)}] {name} (mid={mid})")

        # callout 头 (只保留标题, 不显示签名/认证/UID)
        lines.append(f"> [!note] {i}. {name}")
        lines.append(">")

        # 拉视频
        videos = fetch_user_videos(mid, limit=videos_per_user) if mid else []
        if videos:
            ok_count += 1
            for v in videos:
                v_title = (v.get("title") or "").replace("|", "\\|").strip()
                v_plays = fmt_num(v.get("plays", 0))
                v_date = v.get("date") or ""
                v_url = v.get("url") or ""
                # 链接显示文字: 发布日期+标题 拼接 (日期为空时只显示标题)
                link_text = f"{v_date} {v_title}".strip() if v_date else v_title
                lines.append(f"> - [{link_text}]({v_url}) | 播放 {v_plays}")
        else:
            fail_count += 1
            lines.append("> _暂无视频数据_")
        lines.append("")

        # 风控间隔
        if i < len(users):
            time.sleep(random.uniform(1, 2))

    lines.append("---")
    lines.append(f"> 数据来源: opencli bilibili user-videos | 采集时间: {now} | 成功 {ok_count} / 失败 {fail_count}")
    return "\n".join(lines) + "\n"


def main():
    log("=" * 60)
    log("B站关注视频采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出文件: {MD_FILE}")
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

    # 2. 生成 markdown
    md_content = build_markdown(users, videos_per_user)
    MD_FILE.write_text(md_content, encoding="utf-8")
    log(f"已保存: {MD_FILE}")
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
