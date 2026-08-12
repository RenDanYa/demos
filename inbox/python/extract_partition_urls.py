# -*- coding: utf-8 -*-
"""提取分区笔记中所有视频 URL 到 url.md

扫描指定分区 md 文件,
提取表格中的 bilibili 视频 URL, 按行输出到 url.md。

用法:
    python extract_partition_urls.py              # 处理 TARGET_FILES 指定的文件
    python extract_partition_urls.py --all        # 处理分区目录下所有 md 文件
"""
import re
import sys
from pathlib import Path

PARTITION_DIR = Path(r"d:\obsidian\demo\05_long_project\B站\每周必看\分区")
OUTPUT_FILE = Path(r"d:\obsidian\demo\05_long_project\B站\每周必看\url.md")

# 默认处理的文件列表 (空则处理全部)
TARGET_FILES = [
    "计算机技术.md",
    "软件应用.md",
    "设计·创意.md",
]

URL_PATTERN = re.compile(r"https?://[^\s\)]+")


def main():
    urls = []

    # 决定处理的文件列表
    if "--all" in sys.argv:
        md_files = sorted(PARTITION_DIR.glob("*.md"))
        print(f"模式: 处理分区目录下全部 md 文件")
    else:
        md_files = [PARTITION_DIR / f for f in TARGET_FILES]
        md_files = [p for p in md_files if p.exists()]
        print(f"模式: 处理指定文件列表")

    print(f"扫描目录: {PARTITION_DIR}")
    print(f"待处理文件数: {len(md_files)}")
    print(f"文件列表: {[p.name for p in md_files]}")
    print()

    for md_path in md_files:
        try:
            content = md_path.read_text(encoding="utf-8")
            # 提取表格行中的 URL (markdown 链接 [标题](url) 或裸 URL)
            file_urls = []
            for line in content.split("\n"):
                if not line.strip().startswith("|"):
                    continue
                for m in URL_PATTERN.finditer(line):
                    url = m.group(0).rstrip(")")
                    if "bilibili.com/video/" in url:
                        file_urls.append(url)
            if file_urls:
                print(f"  {md_path.name}: {len(file_urls)} 条 URL")
                urls.extend(file_urls)
            else:
                print(f"  {md_path.name}: 0 条 URL (无表格数据)")
        except Exception as e:
            print(f"  读取失败 {md_path.name}: {str(e)[:60]}")

    # 去重 (保持顺序)
    seen = set()
    unique_urls = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    print(f"\n总 URL: {len(urls)} 条")
    print(f"去重后: {len(unique_urls)} 条")

    OUTPUT_FILE.write_text("\n".join(unique_urls) + "\n", encoding="utf-8")
    print(f"已保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
