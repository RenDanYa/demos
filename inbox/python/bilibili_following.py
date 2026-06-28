# -*- coding: utf-8 -*-
"""B站关注列表采集 (静态展示, 手动刷新)

只负责拉取关注列表, 输出为表格 Markdown。
视频信息见 bilibili_videos.py (独立组件)。

用法:
    python bilibili_following.py                          # 默认取前 50 个关注
    python bilibili_following.py --limit 100             # 取前 100 个
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OPENCLI_CMD,
    OUTPUT_ROOT,
    log,
    run_opencli,
)

OUTPUT_DIR = OUTPUT_ROOT.parent / "B站关注"  # d:\obsidian\demo\05_long_project\B站关注
MD_FILE = OUTPUT_DIR / "关注列表.md"
CACHE_FILE = OUTPUT_DIR / "following_cache.json"  # 供视频脚本复用
TIMEOUT = 60


def fetch_following_page(page=1, limit=50):
    ok, stdout, err = run_opencli(
        ["bilibili", "following", "--page", str(page), "--limit", str(limit), "-f", "json"],
        TIMEOUT,
    )
    if not ok:
        log(f"following 调用失败 (page={page}): {err}")
        return [], 0
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data, 0
        if isinstance(data, dict) and "list" in data:
            return data["list"], data.get("total", 0)
    except json.JSONDecodeError as e:
        log(f"following JSON 解析失败: {e}")
    return [], 0


def fetch_all_following(limit_total=50):
    all_users = []
    page = 1
    while len(all_users) < limit_total:
        page_limit = min(50, limit_total - len(all_users))
        users, _ = fetch_following_page(page=page, limit=page_limit)
        if not users:
            break
        all_users.extend(users)
        if len(users) < page_limit:
            break
        page += 1
        if page > 10:
            log(f"达到 10 页安全上限, 停止翻页")
            break
    return all_users[:limit_total]


def build_markdown(users):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "---",
        "tags: [B站, 关注列表]",
        f"更新时间: {now}",
        f"关注总数: {len(users)}",
        "---",
        "",
        "# B站关注列表",
        "",
        f"> **最近更新**: {now} | **共 {len(users)} 人**",
        "",
        "| # | 昵称 | 签名 | 关系 | 认证 | UID |",
        "|---|------|------|------|------|-----|",
    ]
    for i, u in enumerate(users, 1):
        name = (u.get("name") or "").replace("|", "\\|").replace("\n", " ").strip()
        sign = (u.get("sign") or "").replace("|", "\\|").replace("\n", " ").strip()
        following = u.get("following") or ""
        fans = (u.get("fans") or "").replace("|", "\\|").strip()
        mid = u.get("mid") or ""
        lines.append(f"| {i} | {name} | {sign[:50]} | {following} | {fans} | {mid} |")
    lines.append("")
    lines.append(f"> 数据来源: opencli bilibili following | 采集时间: {now}")
    return "\n".join(lines) + "\n"


def main():
    log("=" * 60)
    log("B站关注列表采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出文件: {MD_FILE}")
    log("=" * 60)

    limit = 50
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
            except ValueError:
                pass

    log(f"目标数量: {limit}")
    log("调用 bilibili following 中...")
    users = fetch_all_following(limit)
    if not users:
        log("未获取到关注列表, 可能未登录或风控")
        return 2

    log(f"获取到 {len(users)} 个关注")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MD_FILE.write_text(build_markdown(users), encoding="utf-8")
    # 缓存 mid + name 供视频脚本复用 (避免再调一次 following)
    CACHE_FILE.write_text(
        json.dumps([{"mid": u.get("mid"), "name": u.get("name"), "sign": u.get("sign", ""),
                     "fans": u.get("fans", "")} for u in users],
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"已保存: {MD_FILE}")
    log(f"已缓存: {CACHE_FILE}")
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
