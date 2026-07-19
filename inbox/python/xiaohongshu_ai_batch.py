# -*- coding: utf-8 -*-
"""小红书点点 AI 批量问答采集

读取问题清单文件 (每行一个问题, 支持 `- 问题` 或纯文本), 逐个调用
xiaohongshu_ai 的搜索逻辑, 生成多个 Obsidian Markdown 文件。

用法:
    python xiaohongshu_ai_batch.py                                    # 默认读 问题清单.md
    python xiaohongshu_ai_batch.py "d:\\path\\to\\questions.md"       # 指定清单文件
"""

import random
import re
import sys
import time
from pathlib import Path

# 复用 xiaohongshu_ai 的搜索/生成逻辑
sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_ai import (  # noqa: E402
    AI_OUTPUT_ROOT,
    TIMEOUT_AI,
    build_markdown,
    call_search_ai,
    log,
    write_markdown,
)
from xiaohongshu_collect import sanitize_filename  # noqa: E402

# ============ 配置 ============
DEFAULT_LIST_FILE = r"d:\obsidian\demo\inbox\问题清单.md"

# 防风控: 每次搜索之间的间隔 (秒) — AI 问答比商品搜索更敏感, 间隔更长
INTERVAL_MIN = 10
INTERVAL_MAX = 20
# 批次休息: 每搜完 N 个问题后长休息
BATCH_SIZE = 3
BATCH_REST_MIN = 30
BATCH_REST_MAX = 60


def parse_list_file(file_path):
    """解析清单文件, 返回问题列表

    支持:
      - `- 问题` (Markdown 列表)
      - `1. 问题` (有序列表)
      - `问题` (纯文本)
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
    """tkinter 弹窗: 清单文件路径"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = simpledialog.askstring(
        "小红书 AI 批量问答",
        "请输入问题清单文件路径:",
        initialvalue=DEFAULT_LIST_FILE,
        parent=root,
    )
    root.destroy()
    return file_path.strip() if (file_path and file_path.strip()) else None


def process_one_question(query, index, total):
    """处理单个问题: 调用 AI + 生成 markdown, 返回 (ok, path_or_error)"""
    log(f"[{index}/{total}] {query}")
    log("  调用 search-ai 中, 请稍候 (约 30-60 秒)...")

    # 第一次尝试
    sections = call_search_ai(query, timeout=30)

    if not sections:
        # 重试一次 (不带 debug, debug 仅用于诊断)
        log("  AI 未返回内容, 重试一次...")
        if index > 1:
            time.sleep(random.uniform(5, 10))
        sections = call_search_ai(query, timeout=40)
        if not sections:
            return False, "AI 未返回内容"

    # 过滤调试行 (section 以 _ 开头)
    real_sections = [s for s in sections if not str(s.get("section", "")).startswith("_")]
    if not real_sections:
        return False, f"仅得到调试信息"

    log(f"  获取到 {len(real_sections)} 个 section")
    md_content = build_markdown(query, real_sections)
    md_path = write_markdown(query, md_content)
    return True, str(md_path)


def main():
    log("=" * 60)
    log("小红书点点 AI 批量问答采集 启动")
    log("=" * 60)

    # 1. 获取清单文件路径
    list_file = DEFAULT_LIST_FILE
    if len(sys.argv) >= 2:
        list_file = sys.argv[1].strip()
    else:
        list_file = show_batch_dialog()

    if not list_file:
        log("未指定清单文件, 退出")
        return 1

    # 2. 解析清单
    items = parse_list_file(list_file)
    if not items:
        log(f"清单为空或无法解析: {list_file}")
        return 1

    log(f"清单文件: {list_file}")
    log(f"共 {len(items)} 个问题")
    log(f"输出目录: {AI_OUTPUT_ROOT}")
    log("-" * 60)

    # 3. 逐个处理
    results = []
    total = len(items)
    start_time = time.time()

    for i, query in enumerate(items, 1):
        # 间隔 (第 2 条起)
        if i > 1:
            wait = random.uniform(INTERVAL_MIN, INTERVAL_MAX)
            time.sleep(wait)

        # 批次休息
        if i > 1 and (i - 1) % BATCH_SIZE == 0:
            rest = random.uniform(BATCH_REST_MIN, BATCH_REST_MAX)
            log(f"  已处理 {i-1}/{total}, 批次休息 {rest:.0f} 秒...")
            time.sleep(rest)

        # 搜索 + 生成 markdown
        try:
            ok, info = process_one_question(query, i, total)
            if ok:
                log(f"  OK -> {Path(info).name}")
                results.append({"status": "ok", "query": query, "path": info})
            else:
                log(f"  失败: {info}")
                results.append({"status": "fail", "query": query, "error": info})
        except Exception as e:
            log(f"  异常: {e}")
            results.append({"status": "fail", "query": query, "error": str(e)})

    # 4. 汇总
    elapsed = time.time() - start_time
    ok_count = sum(1 for r in results if r["status"] == "ok")
    fail_count = len(results) - ok_count

    log("=" * 60)
    log(f"批量采集完成: 成功 {ok_count}/{total}, 失败 {fail_count}, 用时 {elapsed:.0f}s")

    if fail_count:
        log("失败列表:")
        for r in results:
            if r["status"] != "ok":
                log(f"  - {r['query'][:30]}: {r.get('error', '?')}")

    return 0 if fail_count == 0 else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
