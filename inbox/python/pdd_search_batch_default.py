# -*- coding: utf-8 -*-
"""拼多多批量搜索 (综合排序)

读取待购清单文件 (每行一个商品名, 支持 `- item` 或纯文本), 逐个调用
pdd_search 的搜索逻辑 (综合排序), 生成多个 Obsidian Markdown 文件。

与 pdd_search_batch.py 的区别:
  - 本脚本使用综合排序 (pdd_search), 文件名无 _低价 后缀
  - pdd_search_batch.py 使用价格升序 (pdd_search_cheap), 文件名带 _低价 后缀

用法:
    python pdd_search_batch_default.py                                    # 默认读 商品购买清单.md, 每个搜 3 个
    python pdd_search_batch_default.py "d:\\path\\to\\list.md"            # 指定清单文件
    python pdd_search_batch_default.py "d:\\path\\to\\list.md" 5          # 每个商品搜 5 个结果
"""

import random
import re
import sys
import time
from pathlib import Path

# 复用 pdd_search 的搜索/生成逻辑 (综合排序)
sys.path.insert(0, str(Path(__file__).parent))
from pdd_search import (  # noqa: E402
    IMAGES_ROOT,
    OUTPUT_ROOT,
    build_markdown,
    log,
    sanitize_filename,
    search_products,
    write_markdown,
)

# ============ 配置 ============
DEFAULT_LIST_FILE = r"d:\obsidian\demo\inbox\商品购买清单.md"
DEFAULT_LIMIT = 3  # 每个商品默认搜索 3 个结果 (批量场景不宜过多)

# 防风控: 每次搜索之间的间隔 (秒)
INTERVAL_MIN = 5
INTERVAL_MAX = 10
# 批次休息: 每搜完 N 个商品后长休息
BATCH_SIZE = 5
BATCH_REST_MIN = 20
BATCH_REST_MAX = 40


def parse_list_file(file_path):
    """解析清单文件, 返回商品名列表

    支持:
      - `- 商品名` (Markdown 列表)
      - `1. 商品名` (有序列表)
      - `商品名` (纯文本)
    跳过空行和注释 (以 # 开头)
    """
    p = Path(file_path)
    if not p.exists():
        log(f"清单文件不存在: {file_path}")
        return []

    items = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 去除前缀: `- `, `* `, `1. `, `- [ ] ` 等
        cleaned = re.sub(r'^[-*]\s*(?:\[[ xX]\]\s*)?', '', line)
        cleaned = re.sub(r'^\d+\.\s*', '', cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            items.append(cleaned)
    return items


def show_batch_dialog():
    """tkinter 弹窗: 清单文件路径 + 每个商品数量"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return None, DEFAULT_LIMIT

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = simpledialog.askstring(
        "拼多多批量搜索 (综合排序)",
        "请输入清单文件路径:",
        initialvalue=DEFAULT_LIST_FILE,
        parent=root,
    )
    if not file_path or not file_path.strip():
        root.destroy()
        return None, 0
    file_path = file_path.strip()

    limit_str = simpledialog.askstring(
        "每个商品数量",
        "每个商品搜索几个结果? (1-20)",
        initialvalue=str(DEFAULT_LIMIT),
        parent=root,
    )
    try:
        limit = max(1, min(20, int(limit_str)))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    root.destroy()
    return file_path, limit


def main():
    log("=" * 60)
    log("拼多多批量搜索 (综合排序) 启动")
    log("=" * 60)

    # 1. 获取清单文件路径 + 每个商品数量
    list_file = DEFAULT_LIST_FILE
    limit = DEFAULT_LIMIT
    if len(sys.argv) >= 2:
        list_file = sys.argv[1].strip()
        if len(sys.argv) >= 3:
            try:
                limit = max(1, min(20, int(sys.argv[2])))
            except ValueError:
                limit = DEFAULT_LIMIT
    else:
        list_file, limit = show_batch_dialog()

    if not list_file:
        log("未指定清单文件, 退出")
        return 1

    # 2. 解析清单
    items = parse_list_file(list_file)
    if not items:
        log(f"清单为空或无法解析: {list_file}")
        return 1

    log(f"清单文件: {list_file}")
    log(f"共 {len(items)} 个商品, 每个搜索 {limit} 个结果")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("-" * 60)

    # 3. 逐个搜索
    results = []
    total = len(items)
    start_time = time.time()

    for i, keyword in enumerate(items, 1):
        log(f"[{i}/{total}] {keyword}")

        # 间隔 (第 2 条起)
        if i > 1:
            wait = random.uniform(INTERVAL_MIN, INTERVAL_MAX)
            time.sleep(wait)

        # 批次休息
        if i > 1 and (i - 1) % BATCH_SIZE == 0:
            rest = random.uniform(BATCH_REST_MIN, BATCH_REST_MAX)
            log(f"  已处理 {i-1}/{total}, 批次休息 {rest:.0f} 秒...")
            time.sleep(rest)

        # 准备图片目录
        images_dir_name = f"pdd_{sanitize_filename(keyword)[:30]}"
        images_dir = IMAGES_ROOT / images_dir_name
        images_dir.mkdir(parents=True, exist_ok=True)

        # 搜索 + 生成 markdown
        try:
            products = search_products(keyword, limit, images_dir)
            if not products:
                log(f"  失败: 未获取到商品")
                results.append({"status": "fail", "keyword": keyword, "error": "无商品"})
                continue

            md_content = build_markdown(keyword, products, images_dir)
            md_path = write_markdown(keyword, md_content)
            log(f"  OK -> {md_path.name} ({len(products)} 个商品)")
            results.append({
                "status": "ok",
                "keyword": keyword,
                "count": len(products),
                "path": str(md_path),
            })
        except Exception as e:
            log(f"  异常: {e}")
            results.append({"status": "fail", "keyword": keyword, "error": str(e)})

    # 4. 汇总
    elapsed = time.time() - start_time
    ok_count = sum(1 for r in results if r["status"] == "ok")
    fail_count = len(results) - ok_count

    log("=" * 60)
    log(f"批量搜索完成: 成功 {ok_count}/{total}, 失败 {fail_count}, 用时 {elapsed:.0f}s")

    if fail_count:
        log("失败列表:")
        for r in results:
            if r["status"] != "ok":
                log(f"  - {r['keyword']}: {r.get('error', '?')}")

    return 0 if fail_count == 0 else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
