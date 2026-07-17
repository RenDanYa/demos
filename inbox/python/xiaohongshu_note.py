# -*- coding: utf-8 -*-
"""小红书单篇笔记采集 (输入 URL)

调用 opencli xiaohongshu note 命令, 把单篇笔记保存为 Obsidian Markdown。
与批量采集 (xiaohongshu_collect.py) 共享输出目录和格式。

用法:
    python xiaohongshu_note.py                          # 弹窗输入 URL
    python xiaohongshu_note.py "https://www.xiaohongshu.com/explore/xxx?xsec_token=..."
"""

import json
import sys
from pathlib import Path

# 复用 xiaohongshu_collect 的工具函数
sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OPENCLI_CMD,
    OUTPUT_ROOT,
    IMAGES_ROOT,
    TIMEOUT_NOTE,
    log,
    run_opencli,
    get_note_full,
    download_images,
    download_media_urls,
    build_markdown,
    sanitize_filename,
    show_input_dialog,
)

# 单篇笔记直接输出到 小红书 根目录, 不建子文件夹
NOTE_OUTPUT_ROOT = OUTPUT_ROOT
TIMEOUT_SINGLE = 90  # note + download, 给足时间


def show_url_input_dialog():
    """tkinter 弹窗: 输入笔记 URL"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        if len(sys.argv) >= 2:
            return sys.argv[1].strip()
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    url = simpledialog.askstring(
        "小红书单篇采集",
        "请输入笔记 URL (从浏览器复制完整链接):",
        initialvalue="https://www.xiaohongshu.com/explore/",
        parent=root,
    )
    root.destroy()
    return url.strip() if url else None


def extract_note_id(url):
    """从 URL 中提取 note_id (路径段中 24 位十六进制)"""
    import re
    m = re.search(r'/(?:explore|search_result|discovery/item)/([a-f0-9]{24})', url)
    if m:
        return m.group(1)
    # 兜底: 取路径中任意 24 位十六进制
    m = re.search(r'([a-f0-9]{24})', url)
    return m.group(1) if m else None


def main():
    log("=" * 60)
    log("小红书单篇笔记采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {NOTE_OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取 URL
    url = None
    if len(sys.argv) >= 2:
        url = sys.argv[1].strip()
    else:
        url = show_url_input_dialog()

    if not url or not url.startswith("http"):
        log("未输入有效 URL, 退出")
        return 1

    log(f"URL: {url}")
    note_id = extract_note_id(url)
    if not note_id:
        log(f"无法从 URL 提取 note_id: {url}")
        return 1
    log(f"note_id: {note_id}")

    # 2. 获取笔记详情 (用 note-full, 保留正文换行, 与批量采集一致)
    log("获取笔记详情中...")
    note_data, comments = get_note_full(url)
    if not note_data:
        log("获取笔记失败, 可能风控或 URL 失效")
        return 2

    title = note_data.get("title") or note_data.get("desc", "")[:30] or note_id
    log(f"标题: {title}")

    # 3. 下载图片 (优先用 note-full 返回的 media URL 直接下载, 回退 download 命令)
    NOTE_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    images_dir = IMAGES_ROOT / note_id
    media_list = note_data.get("_media", [])

    log("下载图片中...")
    if media_list:
        img_files = download_media_urls(media_list, images_dir, note_id)
        if img_files:
            log(f"下载图片: {len(img_files)} 张 (直接下载)")
        else:
            # 回退到 download 命令
            img_files = download_images(url, images_dir)
            log(f"下载图片: {len(img_files)} 张 (download 命令)")
    else:
        img_files = download_images(url, images_dir)
        log(f"下载图片: {len(img_files)} 张 (download 命令)")

    # 4. 生成 markdown (复用 build_markdown, 含评论)
    # images_rel_dir 使用 vault 相对路径 (用于 wikilink)
    images_rel_dir = f"附件/{note_id}"
    # 使用下载函数返回的有序文件列表 (已按笔记显示顺序排列, 避免目录重读导致顺序错乱)
    from pathlib import Path as _P
    if img_files:
        image_files_names = [_P(f).name for f in img_files]
    elif images_dir.exists():
        # 回退: 仅当下载函数未返回文件列表时, 从目录读取
        image_files_names = sorted([f.name for f in images_dir.rglob("*.jpg")] +
                                   [f.name for f in images_dir.rglob("*.png")] +
                                   [f.name for f in images_dir.rglob("*.mp4")])
    else:
        image_files_names = []
    published_at = note_data.get("publishedAt", "")
    md_content = build_markdown(
        note_data.get("title", note_id),
        note_data,
        comments,
        image_files_names,
        images_rel_dir,
        url,
        note_id,
        published_at,
        source_type="单篇采集",
    )

    # 5. 保存
    safe_name = sanitize_filename(title)[:60] or note_id
    md_path = NOTE_OUTPUT_ROOT / f"{safe_name}.md"
    if md_path.exists():
        from datetime import datetime
        ts = datetime.now().strftime("%H%M%S")
        md_path = NOTE_OUTPUT_ROOT / f"{safe_name}_{ts}.md"

    md_path.write_text(md_content, encoding="utf-8")
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
