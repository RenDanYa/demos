# -*- coding: utf-8 -*-
"""修复 BOSS直聘文件状态

检查所有文件的采集完整性，更新错误的"已采集"状态为"采集中"。

用法:
    python boss_fix_status.py
"""

import re
from pathlib import Path

OUTPUT_ROOT = Path(r"d:\obsidian\demo\05_long_project\BOSS直聘")


def parse_frontmatter_status(md_content):
    """解析 Markdown 文件的 frontmatter 中的 status 字段"""
    match = re.search(r'^status:\s*(.+)$', md_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def update_frontmatter_status(md_content, status):
    """更新 Markdown 文件的 frontmatter 中的 status 字段"""
    lines = md_content.split('\n')
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('status:'):
            lines[i] = f'status: {status}'
            updated = True
            break

    if not updated:
        for i, line in enumerate(lines):
            if line == '---' and i > 0:
                lines.insert(i, f'status: {status}')
                break

    return '\n'.join(lines)


def check_collection_complete(md_content):
    """检查采集是否完整"""
    # 解析表格中的职位编号
    table_jobs = set()
    table_pattern = re.compile(r'^\| (\d+) \|', re.MULTILINE)
    for m in table_pattern.finditer(md_content):
        table_jobs.add(int(m.group(1)))

    # 解析已有的详情编号
    detail_jobs = set()
    detail_pattern = re.compile(r'^### (\d+)\. ', re.MULTILINE)
    for m in detail_pattern.finditer(md_content):
        detail_jobs.add(int(m.group(1)))

    # 检查是否所有表格职位都有详情
    missing = table_jobs - detail_jobs
    is_complete = len(missing) == 0

    return is_complete, sorted(missing), len(table_jobs)


def main():
    print("=" * 60)
    print("BOSS直聘文件状态修复")
    print(f"目录: {OUTPUT_ROOT}")
    print("=" * 60)

    if not OUTPUT_ROOT.exists():
        print("目录不存在")
        return 1

    # 查找所有 .md 文件
    md_files = list(OUTPUT_ROOT.glob("*.md"))
    if not md_files:
        print("未找到 Markdown 文件")
        return 0

    print(f"\n共找到 {len(md_files)} 个文件")

    fixed_count = 0
    for md_file in sorted(md_files):
        try:
            content = md_file.read_text(encoding="utf-8")
            status = parse_frontmatter_status(content)

            if status != "已采集":
                # 只修复标记为"已采集"的文件
                continue

            # 验证完整性
            is_complete, missing, total = check_collection_complete(content)

            if is_complete:
                print(f"✓ {md_file.name}: 已采集 (完整 {total}/{total})")
            else:
                # 修复状态
                new_content = update_frontmatter_status(content, "采集中")
                md_file.write_text(new_content, encoding="utf-8")
                print(f"✗ {md_file.name}: 已修复 (采集中) - 缺失 {len(missing)}/{total}: {missing}")
                fixed_count += 1

        except Exception as e:
            print(f"✗ {md_file.name}: 读取失败 - {e}")

    print("\n" + "=" * 60)
    print(f"修复完成: {fixed_count} 个文件状态已更新")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    import sys
    try:
        sys.exit(main())
    except Exception as e:
        print(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)