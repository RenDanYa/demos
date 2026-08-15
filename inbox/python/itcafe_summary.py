# -*- coding: utf-8 -*-
"""整合 IT咖啡馆笔记的视频简介/项目地址模块到汇总笔记

扫描 d:/obsidian/视频/resource/IT咖啡馆*.md,
提取每个笔记的 ## 视频简介 / ## 项目地址 模块,
按发布时间排序后整合到一个汇总笔记中。

用法:
    python itcafe_summary.py
"""
import re
from pathlib import Path

RESOURCE_DIR = Path("d:/obsidian/视频/resource")
OUTPUT_FILE = RESOURCE_DIR / "IT咖啡馆-视频简介汇总.md"


def extract_frontmatter_field(content, field):
    """从 frontmatter 提取字段值"""
    m = re.search(rf'^{field}:\s*"?([^"\n]+)"?\s*$', content, re.MULTILINE)
    return m.group(1).strip() if m else ""


def extract_section(content, section_name):
    """提取 ## section_name 模块内容 (到下一个 ## 或文件末尾)

    返回: (title_line, body) 或 (None, None)
    """
    pattern = rf'^(##\s+{re.escape(section_name)}\s*)$([\s\S]*?)(?=^##\s|\Z)'
    m = re.search(pattern, content, re.MULTILINE)
    if m:
        return m.group(1), m.group(2).strip()
    return None, None


def process_file(md_path):
    """处理单个文件, 返回 (title, pub_time, url, section_title, section_body) 或 None"""
    try:
        content = md_path.read_text(encoding="utf-8")
    except Exception:
        return None

    title = extract_frontmatter_field(content, "作品标题")
    pub_time = extract_frontmatter_field(content, "发布时间")
    url = extract_frontmatter_field(content, "作品网址")

    if not title:
        title = md_path.stem

    # 优先提取 ## 项目地址, 其次 ## 视频简介
    for section_name in ("项目地址", "视频简介"):
        sec_title, sec_body = extract_section(content, section_name)
        if sec_title and sec_body:
            return title, pub_time, url, sec_title, sec_body

    return None


def main():
    md_files = sorted(RESOURCE_DIR.glob("IT咖啡馆*.md"))
    print(f"扫描 IT咖啡馆 文件数: {len(md_files)}")

    entries = []
    for md_path in md_files:
        result = process_file(md_path)
        if result:
            title, pub_time, url, sec_title, sec_body = result
            entries.append({
                "file": md_path,
                "title": title,
                "pub_time": pub_time,
                "url": url,
                "section_title": sec_title,
                "section_body": sec_body,
            })

    print(f"提取到模块的条目: {len(entries)}")

    # 按发布时间排序 (新→旧)
    entries.sort(key=lambda e: e["pub_time"], reverse=True)

    # 生成汇总笔记
    lines = []
    lines.append("---")
    lines.append("title: IT咖啡馆视频简介汇总")
    lines.append(f"创建时间: 2026-08-15")
    lines.append(f"条目数: {len(entries)}")
    lines.append("---")
    lines.append("")
    lines.append("# IT咖啡馆视频简介汇总")
    lines.append("")
    lines.append(f"共整合 **{len(entries)}** 篇 IT咖啡馆笔记的视频简介/项目地址模块, 按发布时间倒序排列。")
    lines.append("")

    # 生成目录
    lines.append("## 目录")
    lines.append("")
    for i, e in enumerate(entries, 1):
        safe_title = e["title"].replace("|", "\\|")
        pub_short = e["pub_time"][:10] if e["pub_time"] else ""
        lines.append(f"{i}. [{safe_title}]({e['file'].name}) ({pub_short})")
    lines.append("")

    # 生成详情
    lines.append("## 详情")
    lines.append("")
    for i, e in enumerate(entries, 1):
        lines.append(f"### {i}. {e['title']}")
        lines.append("")
        lines.append(f"- 发布时间: {e['pub_time']}")
        if e["url"]:
            lines.append(f"- 视频链接: {e['url']}")
        lines.append(f"- 原笔记: [[{e['file'].stem}]]")
        lines.append("")
        lines.append(f"**{e['section_title'].strip()}**")
        lines.append("")
        lines.append(e["section_body"])
        lines.append("")
        lines.append("---")
        lines.append("")

    output = "\n".join(lines)
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(f"已生成汇总笔记: {OUTPUT_FILE}")
    print(f"总条目: {len(entries)}")


if __name__ == "__main__":
    main()
