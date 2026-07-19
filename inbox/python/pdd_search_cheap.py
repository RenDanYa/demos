# -*- coding: utf-8 -*-
"""拼多多商品搜索 - 价格从低到高

调用 opencli pdd search --sort price_asc, 按价格升序返回商品。
服务端排序 + 客户端二次排序 (CLI 内置兜底), 确保结果严格按价格升序。

用法:
    python pdd_search_cheap.py                          # 弹窗输入关键词 + 数量
    python pdd_search_cheap.py "手机壳"                  # 默认采集 10 个
    python pdd_search_cheap.py "手机壳" 5                # 指定数量
"""

import json
import os
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
TIMEOUT_SEARCH = 150  # 搜索 + 图片下载, 给足时间

# CLI 内部浏览器命令超时 (默认 60s 不够搜索+下载, 提高到 120s)
os.environ.setdefault("OPENCLI_BROWSER_COMMAND_TIMEOUT", "120")


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
        "拼多多低价搜索",
        "请输入搜索关键词 (按价格升序):",
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


def parse_price(price_str):
    """从价格字符串中提取数值, 用于排序

    例: '¥3.96' -> 3.96, '¥10' -> 10.0, '' -> float('inf')
    """
    if not price_str:
        return float('inf')
    m = re.search(r'[\d.]+', price_str)
    try:
        return float(m.group()) if m else float('inf')
    except (ValueError, AttributeError):
        return float('inf')


def search_products_cheap(query, limit, images_dir):
    """调用 opencli pdd search (综合排序), 在 Python 中按价格升序重排

    返回: [{rank, title, price, sales, image, url}, ...] (按价格升序)
    """
    args = [
        "pdd", "search", query,
        "--limit", str(limit),
        "--download",
        "--output", str(images_dir),
        "-f", "json",
    ]
    log(f"调用 opencli pdd search (limit={limit}, 综合排序)")
    ok, stdout, err = run_opencli(args, TIMEOUT_SEARCH)
    if not ok:
        log(f"pdd search 调用失败: {err}")
        return None

    try:
        data = json.loads(stdout)
        if not isinstance(data, list):
            log(f"意外的 JSON 结构: {type(data).__name__}")
            return None
    except json.JSONDecodeError as e:
        log(f"JSON 解析失败: {e}")
        log(f"原始 stdout 前 300 字符: {stdout[:300] if stdout else '(空)'}")
        return None

    # 在 Python 中按价格升序排序 (CLI 返回的是综合排序)
    data.sort(key=lambda p: parse_price(p.get("price", "")))
    # 重新编号 rank
    for i, p in enumerate(data, 1):
        p["rank"] = i
    log(f"已按价格升序重排 {len(data)} 个商品")
    return data


def to_wikilink_path(local_path, obsidian_root):
    """将本地图片路径转为 Obsidian wikilink 相对路径"""
    try:
        rel = Path(local_path).relative_to(obsidian_root)
        return str(rel).replace("\\", "/")
    except (ValueError, TypeError):
        return str(local_path).replace("\\", "/")


def build_markdown(query, products, images_dir):
    """生成 Obsidian markdown (表格形式, 价格升序)

    products: [{rank, title, price, sales, image, url}, ...]
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_title = re.sub(r"[\r\n]+", " ", query)[:50]

    lines = [
        "---",
        "tags: [拼多多, 商品搜索, 低价排序]",
        f'title: "拼多多低价搜索 - {safe_title}"',
        f"query: {json.dumps(query, ensure_ascii=False)}",
        'source: "拼多多搜索"',
        f"count: {len(products)}",
        "sort: price_asc",
        f"createTime: {datetime.now().isoformat(timespec='seconds')}",
        "status: 已采集",
        "---",
        "",
        f"# 拼多多低价搜索 - {query}",
        "",
        f"> **关键词**: {query} | **数量**: {len(products)} | **排序**: 价格升序 | **时间**: {now}",
        "",
        "## 商品列表 (价格从低到高)",
        "",
        "| # | 图片 | 商品 | 价格 | 销量 |",
        "|---|------|------|------|------|",
    ]

    for p in products:
        rank = p.get("rank", "")
        title = p.get("title", "无标题").replace("|", "\\|").replace("\n", " ")
        price = p.get("price", "")
        sales = p.get("sales", "").replace("|", "\\|")
        image = p.get("image", "")
        url = p.get("url", "")

        if url:
            product_cell = f"[{title}]({url})"
        else:
            product_cell = title

        if image:
            if image.startswith("http"):
                image_cell = f"![{title}]({image})"
            else:
                wiki_path = to_wikilink_path(image, OBSIDIAN_ROOT)
                image_cell = f"![[{wiki_path}\\|300]]"
        else:
            image_cell = ""

        lines.append(f"| {rank} | {image_cell} | {product_cell} | {price} | {sales} |")

    lines.append("")
    return "\n".join(lines)


def write_markdown(query, md_content):
    """保存 markdown 文件, 返回路径"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(query)[:60] or "untitled"
    # 文件名加 _低价 后缀, 区分普通搜索
    md_path = OUTPUT_ROOT / f"{safe_name}_低价.md"

    if md_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        md_path = OUTPUT_ROOT / f"{safe_name}_低价_{ts}.md"

    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def main():
    log("=" * 60)
    log("拼多多低价搜索 (价格升序) 启动")
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

    # 2. 准备图片目录 (与普通搜索共用, 同关键词的图片可复用)
    images_dir_name = f"pdd_{sanitize_filename(query)[:30]}"
    images_dir = IMAGES_ROOT / images_dir_name
    images_dir.mkdir(parents=True, exist_ok=True)

    # 3. 调用 opencli pdd search --sort price_asc
    log("搜索中, 请稍候 (约 15-30 秒)...")
    products = search_products_cheap(query, limit, images_dir)

    if not products:
        log("未获取到商品, 退出")
        return 2

    log(f"获取到 {len(products)} 个商品 (价格升序)")

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
