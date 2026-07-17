# -*- coding: utf-8 -*-
"""小红书博主笔记采集 (输入博主主页 URL)

调用 opencli xiaohongshu user 获取博主发布的笔记列表,
再逐篇采集正文/评论/图片, 保存为 Obsidian Markdown。
与批量采集 (xiaohongshu_collect.py) 共享输出目录和格式。

用法:
    python xiaohongshu_user.py             # 弹窗输入博主主页 URL
    python xiaohongshu_user.py "https://www.xiaohongshu.com/user/profile/xxx?xsec_token=..."
    python xiaohongshu_user.py "URL" 50    # 指定采集数量
"""

import json
import re
import sys
import time
import random
from datetime import datetime
from pathlib import Path

# 复用 xiaohongshu_collect 的工具函数
sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OPENCLI_CMD,
    OUTPUT_ROOT,
    IMAGES_ROOT,
    TIMEOUT_NOTE,
    TIMEOUT_COMMENTS,
    log,
    run_opencli,
    get_note_full,
    download_images,
    build_markdown,
    sanitize_filename,
    extract_note_id,
    # 防风控参数
    INTERVAL_MIN,
    INTERVAL_MAX,
    BATCH_SIZE,
    BATCH_REST_MIN,
    BATCH_REST_MAX,
    FAIL_THRESHOLD,
    FAIL_PAUSE_MIN,
    FAIL_PAUSE_MAX,
)

# user 命令需要滚动加载多页, 给足时间
TIMEOUT_USER = 120

# 笔记保存到 OUTPUT_ROOT (与批量采集一致, 不建子文件夹)
# 图片保存到 IMAGES_ROOT / {note_id} /


def show_url_input_dialog():
    """tkinter 弹窗: 博主主页 URL + 数量"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        if len(sys.argv) >= 2:
            url = sys.argv[1].strip()
            limit = int(sys.argv[2]) if len(sys.argv) >= 3 else 100
            return url, limit
        return None, 0

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    url = simpledialog.askstring(
        "小红书博主采集",
        "请输入博主主页 URL (从浏览器复制完整链接):",
        initialvalue="https://www.xiaohongshu.com/user/profile/",
        parent=root,
    )
    if not url or not url.strip():
        root.destroy()
        return None, 0
    url = url.strip()

    limit_str = simpledialog.askstring(
        "采集数量",
        "采集前几篇笔记? (1-200)",
        initialvalue="100",
        parent=root,
    )
    try:
        limit = max(1, min(200, int(limit_str)))
    except (TypeError, ValueError):
        limit = 100

    root.destroy()
    return url, limit


def extract_user_id(url):
    """从 URL 提取 user_id"""
    m = re.search(r"/user/profile/([a-zA-Z0-9]+)", url)
    return m.group(1) if m else None


def fetch_user_notes(url, limit):
    """调用 opencli xiaohongshu user 获取笔记列表

    返回: [{id, title, type, likes, cover, url}, ...]
    """
    log(f"获取博主笔记列表 (limit={limit})...")
    ok, stdout, err = run_opencli(
        ["xiaohongshu", "user", url, "--limit", str(limit), "-f", "json"],
        TIMEOUT_USER,
    )
    if not ok:
        log(f"user 命令失败: {err}")
        return []
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError as e:
        log(f"JSON 解析失败: {e}")
    return []


def collect_user_notes(url, limit):
    """主采集流程: 获取笔记列表 -> 逐篇采集正文/图片/评论 -> 保存 markdown"""
    user_id = extract_user_id(url)
    if not user_id:
        log(f"无法从 URL 提取 user_id: {url}")
        return []

    # 1. 获取笔记列表
    notes = fetch_user_notes(url, limit)
    if not notes:
        log("无笔记或获取失败, 退出")
        return []

    log(f"博主共 {len(notes)} 篇笔记, 开始逐篇采集")
    log("-" * 40)

    # 2. 逐篇采集
    results = []
    consecutive_fails = 0
    total = len(notes)
    author_name = ""  # 从第一篇笔记获取博主名, 用作子目录名

    for i, item in enumerate(notes, 1):
        note_url = item.get("url", "")
        title = item.get("title", "?")
        note_id_from_list = item.get("id", "")

        if not note_url:
            log(f"[{i}/{total}] 无 URL, 跳过")
            continue

        log(f"[{i}/{total}] {title[:30]}...")

        # 间隔 (第 2 条起)
        if i > 1:
            wait = random.uniform(INTERVAL_MIN, INTERVAL_MAX)
            time.sleep(wait)

        # 批次休息
        if i > 1 and (i - 1) % BATCH_SIZE == 0:
            rest = random.uniform(BATCH_REST_MIN, BATCH_REST_MAX)
            log(f"  已处理 {i-1} 篇, 批次休息 {rest:.0f} 秒...")
            time.sleep(rest)

        # 重试 3 次
        success = False
        last_err = ""
        for attempt in range(3):
            try:
                note_data, comments = get_note_full(note_url)
                if not note_data:
                    raise RuntimeError("note-full 返回空")

                # 获取博主名 (用于日志, 仅第一次)
                if not author_name:
                    author_name = note_data.get("author", "") or user_id
                    log(f"博主: {author_name}")

                # note_id: 优先用列表返回的 id, 回退到 URL 解析
                note_id = note_id_from_list or extract_note_id(note_url)
                if not note_id:
                    note_id = f"unknown_{i}"

                # 下载图片 (优先用 note-full 返回的 media URL, 回退 download 命令)
                images_dir = IMAGES_ROOT / note_id
                images_rel_dir = f"附件/{note_id}"
                image_files = download_images(
                    note_url, images_dir, media_list=note_data.get("_media", [])
                )

                # 生成 markdown
                published_at = note_data.get("publishedAt", "")
                md_content = build_markdown(
                    author_name, note_data, comments, image_files,
                    images_rel_dir, note_url, note_id,
                    published_at=published_at,
                    source_type="博主采集",
                )

                # 保存到小红书根目录 (与其他采集脚本一致, 不建子文件夹)
                md_title = note_data.get("title", "") or title
                safe_name = sanitize_filename(md_title)[:60] or note_id
                md_path = OUTPUT_ROOT / f"{safe_name}.md"
                if md_path.exists():
                    ts = datetime.now().strftime("%H%M%S")
                    md_path = OUTPUT_ROOT / f"{safe_name}_{ts}.md"
                md_path.write_text(md_content, encoding="utf-8")
                log(f"  OK -> {md_path.name}")

                results.append({
                    "status": "ok",
                    "url": note_url,
                    "title": note_data.get("title", title),
                    "path": str(md_path),
                })
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
                "url": note_url,
                "title": title,
                "error": last_err,
            })
            consecutive_fails += 1
            if consecutive_fails >= FAIL_THRESHOLD:
                pause = random.uniform(FAIL_PAUSE_MIN, FAIL_PAUSE_MAX)
                log(f"  连续失败 {consecutive_fails} 次, 暂停 {pause:.0f} 秒...")
                time.sleep(pause)
                consecutive_fails = 0

    return results


def main():
    log("=" * 60)
    log("小红书博主笔记采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取 URL + 数量
    url = None
    limit = 100
    if len(sys.argv) >= 2:
        url = sys.argv[1].strip()
        if len(sys.argv) >= 3:
            try:
                limit = max(1, min(200, int(sys.argv[2])))
            except ValueError:
                limit = 100
    else:
        url, limit = show_url_input_dialog()

    if not url or not url.startswith("http"):
        log("未输入有效 URL, 退出")
        return 1

    log(f"博主主页: {url}")
    log(f"采集数量: {limit}")

    # 2. 采集
    start = time.time()
    results = []
    try:
        results = collect_user_notes(url, limit)
    except Exception as e:
        log(f"采集异常 (已采集 {len(results)} 篇): {e}")
        import traceback
        traceback.print_exc()
    elapsed = time.time() - start

    ok_count = sum(1 for r in results if r["status"] == "ok")
    fail_count = len(results) - ok_count
    log("=" * 40)
    log(f"采集完成: 成功 {ok_count}/{len(results)}, 失败 {fail_count}, 用时 {elapsed:.0f}s")

    if fail_count:
        log("失败列表:")
        for r in results:
            if r["status"] != "ok":
                log(f"  - {r.get('title', '?')[:30]}: {r.get('error', '?')}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
