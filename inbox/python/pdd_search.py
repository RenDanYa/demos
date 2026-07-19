# -*- coding: utf-8 -*-
"""拼多多商品搜索采集

调用 opencli pdd search 命令, 把搜索结果(标题/价格/销量/图片)保存为 Obsidian Markdown。
图片通过 CLI 的 --download 参数自动下载到 Obsidian 附件目录。

用法:
    python pdd_search.py                          # 弹窗输入关键词 + 数量
    python pdd_search.py "手机壳"                  # 默认采集 10 个
    python pdd_search.py "手机壳" 5                # 指定数量
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

# 复用 xiaohongshu_collect 的工具函数 (OPENCLI_CMD / log / run_opencli 等)
sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OPENCLI_CMD,
    OBSIDIAN_ROOT,
    log,
    run_opencli,
    sanitize_filename,
)

# ============ 配置 ============
OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "拼多多"
IMAGES_ROOT = OBSIDIAN_ROOT / "inbox" / "附件"
TIMEOUT_SEARCH = 90  # 搜索 + 图片下载, 给足时间


def show_search_dialog():
    """tkinter 弹窗: 关键词 + 数量"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        if len(sys.argv) >= 2:
            kw = sys.argv[1].strip()
            limit = int(sys.argv[2]) if len(sys.argv) >= 3 else 10
            return kw, limit
        return None, 0

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    kw = simpledialog.askstring(
        "拼多多商品搜索",
        "请输入搜索关键词:",
        initialvalue="手机壳",
        parent=root,
    )
    if not kw or not kw.strip():
        root.destroy()
        return None, 0
    kw = kw.strip()

    limit_str = simpledialog.askstring(
        "采集数量",
        f"搜索「{kw}」前几个商品? (1-50)",
        initialvalue="10",
        parent=root,
    )
    try:
        limit = max(1, min(50, int(limit_str)))
    except (TypeError, ValueError):
        limit = 10

    root.destroy()
    return kw, limit


def search_products(query, limit, images_dir):
    """调用 opencli pdd search, 下载图片到 images_dir

    返回: [{rank, title, price, sales, image, url}, ...]
    image 字段为本地文件路径 (下载成功) 或原始 URL (下载失败)
    """
    args = [
        "pdd", "search", query,
        "--limit", str(limit),
        "--download",
        "--output", str(images_dir),
        "-f", "json",
    ]
    log(f"调用 opencli pdd search (limit={limit}, 下载图片到 {images_dir.name}/)")
    ok, stdout, err = run_opencli(args, TIMEOUT_SEARCH)
    if not ok:
        log(f"pdd search 调用失败: {err}")
        return None

    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        log(f"意外的 JSON 结构: {type(data).__name__}")
        return None
    except json.JSONDecodeError as e:
        log(f"JSON 解析失败: {e}")
        log(f"原始 stdout 前 300 字符: {stdout[:300] if stdout else '(空)'}")
        return None


def to_wikilink_path(local_path, obsidian_root):
    """将本地图片路径转为 Obsidian wikilink 相对路径

    例: D:\\obsidian\\demo\\inbox\\附件\\pdd_手机壳\\1_xxx.jpeg
        -> 附件/pdd_手机壳/1_xxx.jpeg
    """
    try:
        rel = Path(local_path).relative_to(obsidian_root)
        return str(rel).replace("\\", "/")
    except (ValueError, TypeError):
        # 路径不在 obsidian_root 下, 或是 URL (下载失败时保留原始 URL)
        return str(local_path).replace("\\", "/")


def build_markdown(query, products, images_dir):
    """生成 Obsidian markdown

    products: [{rank, title, price, sales, image, url}, ...]
    images_dir: 图片下载目录 (Path)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_title = re.sub(r"[\r\n]+", " ", query)[:50]
    wiki_dir = to_wikilink_path(str(images_dir), OBSIDIAN_ROOT)

    lines = [
        "---",
        "tags: [拼多多, 商品搜索]",
        f'title: "拼多多搜索 - {safe_title}"',
        f"query: {json.dumps(query, ensure_ascii=False)}",
        'source: "拼多多搜索"',
        f"count: {len(products)}",
        f"createTime: {datetime.now().isoformat(timespec='seconds')}",
        "status: 已采集",
        "---",
        "",
        f"# 拼多多搜索 - {query}",
        "",
        f"> **关键词**: {query} | **数量**: {len(products)} | **时间**: {now}",
        "",
        "## 商品列表",
        "",
    ]

    for p in products:
        rank = p.get("rank", "")
        title = p.get("title", "无标题")
        price = p.get("price", "")
        sales = p.get("sales", "")
        image = p.get("image", "")
        url = p.get("url", "")

        lines.append(f"### {rank}. {title}")
        lines.append("")
        lines.append(f"- **价格**: {price}")
        if sales:
            lines.append(f"- **销量**: {sales}")
        if url:
            lines.append(f"- **链接**: [查看商品]({url})")
        lines.append("")

        # 图片: 本地路径用 wikilink, URL 用 markdown 图片语法
        if image:
            if image.startswith("http"):
                # 下载失败, 保留原始 URL
                lines.append(f"![{title}]({image})")
            else:
                # 本地文件 -> Obsidian wikilink
                wiki_path = to_wikilink_path(image, OBSIDIAN_ROOT)
                lines.append(f"![[{wiki_path}|300]]")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def write_markdown(query, md_content):
    """保存 markdown 文件, 返回路径"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(query)[:60] or "untitled"
    md_path = OUTPUT_ROOT / f"{safe_name}.md"

    # 同名文件已存在时, 加时间戳后缀避免覆盖
    if md_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        md_path = OUTPUT_ROOT / f"{safe_name}_{ts}.md"

    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def main():
    log("=" * 60)
    log("拼多多商品搜索采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取关键词 + 数量
    query = None
    limit = 10
    if len(sys.argv) >= 2:
        query = sys.argv[1].strip()
        if len(sys.argv) >= 3:
            try:
                limit = max(1, min(50, int(sys.argv[2])))
            except ValueError:
                limit = 10
    else:
        query, limit = show_search_dialog()

    if not query:
        log("未输入关键词, 退出")
        return 1

    log(f"关键词: {query}")
    log(f"数量: {limit}")

    # 2. 准备图片目录
    images_dir_name = f"pdd_{sanitize_filename(query)[:30]}"
    images_dir = IMAGES_ROOT / images_dir_name
    images_dir.mkdir(parents=True, exist_ok=True)

    # 3. 调用 opencli pdd search (含图片下载)
    log("搜索中, 请稍候 (约 15-30 秒)...")
    products = search_products(query, limit, images_dir)

    if not products:
        log("未获取到商品, 退出")
        return 2

    log(f"获取到 {len(products)} 个商品")

    # 4. 生成 markdown
    md_content = build_markdown(query, products, images_dir)
    md_path = write_markdown(query, md_content)
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
