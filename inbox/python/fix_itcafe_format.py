# -*- coding: utf-8 -*-
"""修复 IT咖啡馆-*.md 笔记格式

问题:
1. 列表项被误写为二级标题: `## - xxx` 应为 `- xxx`
2. 列表项中嵌套二级标题: `* ## xxx` 应为 `* xxx`
3. 二级标题误用为内容: `## xxx` 应为 `- xxx` (描述性文字非章节标题)

处理: 将所有 `## xxx` 形式转为无序列表项, 并删除前面空行让列表连续。
注意: 不影响 `### ` (三级标题, 正常章节标题) 和 `# ` (一级标题)。

用法:
    python fix_itcafe_format.py          # 处理 d:\\obsidian\\视频\\resource\\IT咖啡馆-*.md
"""
import re
import sys
from pathlib import Path

RESOURCE_DIR = Path(r"d:\obsidian\视频\resource")

# 匹配三种误用:
# 1. `## - xxx` (二级标题误用为列表项, 带 - 前缀)
# 2. `* ## xxx` 或 `- ## xxx` (列表项中嵌套二级标题)
# 3. `## xxx` (二级标题误用为内容, 纯描述性文字)
BAD_HEADING_PATTERN_1 = re.compile(r"^##\s+-\s+(.*)$")
BAD_HEADING_PATTERN_2 = re.compile(r"^([*\-])\s+##\s+(.*)$")
BAD_HEADING_PATTERN_3 = re.compile(r"^##\s+(.*)$")


def fix_content(content):
    """修复内容

    1. `## - xxx` → `- xxx` (二级标题误用为列表项)
    2. `* ## xxx` / `- ## xxx` → `* xxx` / `- xxx` (列表项中嵌套二级标题)
    3. `## xxx` → `- xxx` (二级标题误用为内容)
    4. 删除该行前面的空行, 让列表连续
    """
    lines = content.split("\n")
    new_lines = []
    fixed_count = 0
    frontmatter_done = False
    in_frontmatter = False

    for i, line in enumerate(lines):
        # frontmatter 检测: 仅文件开头第一个 --- 到第二个 ---
        if line.strip() == "---" and not frontmatter_done:
            in_frontmatter = not in_frontmatter
            if not in_frontmatter:
                frontmatter_done = True
            new_lines.append(line)
            continue
        if in_frontmatter:
            new_lines.append(line)
            continue

        m1 = BAD_HEADING_PATTERN_1.match(line)
        m2 = BAD_HEADING_PATTERN_2.match(line)
        m3 = BAD_HEADING_PATTERN_3.match(line)
        if m1:
            # `## - xxx` → `- xxx`
            new_line = f"- {m1.group(1)}"
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            new_lines.append(new_line)
            fixed_count += 1
        elif m2:
            # `* ## xxx` → `* xxx`
            new_line = f"{m2.group(1)} {m2.group(2)}"
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            new_lines.append(new_line)
            fixed_count += 1
        elif m3:
            # `## xxx` → `- xxx`
            new_line = f"- {m3.group(1)}"
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            new_lines.append(new_line)
            fixed_count += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines), fixed_count


def main():
    md_files = sorted(RESOURCE_DIR.glob("IT咖啡馆-*.md"))
    print(f"扫描目录: {RESOURCE_DIR}")
    print(f"IT咖啡馆 文件数: {len(md_files)}")
    print()

    total_fixed = 0
    affected_files = 0

    for md_path in md_files:
        try:
            content = md_path.read_text(encoding="utf-8")
            new_content, fixed_count = fix_content(content)

            if fixed_count > 0:
                md_path.write_text(new_content, encoding="utf-8")
                print(f"  ✓ {md_path.name}: 修复 {fixed_count} 处")
                total_fixed += fixed_count
                affected_files += 1
        except Exception as e:
            print(f"  ✗ {md_path.name}: {str(e)[:60]}")

    print()
    print(f"影响文件: {affected_files} 个")
    print(f"总修复数: {total_fixed} 处")


if __name__ == "__main__":
    main()
