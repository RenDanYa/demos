# -*- coding: utf-8 -*-
"""重新生成分区笔记文件

读取指定的分区 md 文件, 解析表格数据行, 用最新 frontmatter 格式重新写入。
不重新调用 weekly API, 基于现有数据重建。

用法:
    python regen_partition_files.py  # 重新生成默认 3 个文件
"""
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import log  # noqa: E402

PARTITION_DIR = Path(r"d:\obsidian\demo\05_long_project\B站\每周必看\分区")

# 默认重新生成的文件
TARGET_FILES = [
    "计算机技术.md",
    "软件应用.md",
    "设计·创意.md",
]


def parse_table_rows(content):
    """从 md 内容中提取表格数据行 (排除表头和分隔符)

    返回: list[str] 数据行 (按原顺序)
    """
    lines = content.split("\n")
    rows = []
    in_table = False
    header_passed = False

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        # 跳过表头行 (含 "期数")
        if "期数" in stripped and "标题" in stripped:
            in_table = True
            header_passed = False
            continue

        # 跳过分隔符行 (含 ---)
        if in_table and not header_passed and "---" in stripped:
            header_passed = True
            continue

        # 数据行
        if in_table and header_passed:
            rows.append(line)

    return rows


def sort_rows_by_episode(rows):
    """按期数倒序排序表格行 (最新在顶部)

    表格行格式: | 年 | 月 | 周 | 期数 | ...
    """
    def get_episode_num(row):
        cells = [c.strip() for c in row.split("|")]
        # cells[0]="" [1]=年 [2]=月 [3]=周 [4]=期数
        if len(cells) >= 5:
            try:
                return int(cells[4])
            except ValueError:
                pass
        return 0

    return sorted(rows, key=get_episode_num, reverse=True)


def rebuild_file(md_path, partition_name):
    """重新生成单个分区文件

    1. 读取现有内容
    2. 提取表格数据行
    3. 按期数倒序排序
    4. 用最新 frontmatter 格式重新写入
    """
    content = md_path.read_text(encoding="utf-8")
    rows = parse_table_rows(content)

    if not rows:
        log(f"  ⚠ {md_path.name}: 未找到表格数据行, 跳过")
        return False

    # 按期数倒序排序
    sorted_rows = sort_rows_by_episode(rows)

    # 统计期数
    episode_nums = set()
    for row in sorted_rows:
        cells = [c.strip() for c in row.split("|")]
        if len(cells) >= 5:
            try:
                episode_nums.add(int(cells[4]))
            except ValueError:
                pass

    # 用最新格式重新写入
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_iso = datetime.now().isoformat(timespec="seconds")

    header_lines = [
        "---",
        "tags: [B站, 每周必看, 分区]",
        f'title: "B站每周必看 - {partition_name}"',
        f"partition: {__import__('json').dumps(partition_name, ensure_ascii=False)}",
        f"createTime: {now_iso}",
        f"updateTime: {now_iso}",
        "status: 持续追加",
        "---",
        "",
        f"# B站每周必看 - {partition_name}",
        "",
        f"> 分区笔记, 按期数倒序排列 (最新在顶部)。最后更新: {now}",
        "",
        "| 年 | 月 | 周 | 期数 | 标题 | UP主 | 时长 | 发布 | 播放 | 点赞 | 投币 |",
        "|----|----|----|------|------|------|------|------|------|------|------|",
    ]

    new_content = "\n".join(header_lines) + "\n" + "\n".join(sorted_rows) + "\n"
    md_path.write_text(new_content, encoding="utf-8")

    log(f"  ✓ {md_path.name}: {len(sorted_rows)} 行, {len(episode_nums)} 期")
    return True


def main():
    log("=" * 60)
    log("重新生成分区笔记 启动")
    log(f"目标文件: {TARGET_FILES}")
    log("=" * 60)

    # 备份
    import shutil
    backup_dir = PARTITION_DIR / "_backup_regen"
    backup_dir.mkdir(exist_ok=True)
    log(f"备份目录: {backup_dir}")

    for fname in TARGET_FILES:
        md_path = PARTITION_DIR / fname
        if not md_path.exists():
            log(f"  ⚠ {fname}: 文件不存在, 跳过")
            continue

        # 备份
        backup_path = backup_dir / fname
        shutil.copy2(md_path, backup_path)

        # 从文件名提取分区名 (去掉 .md)
        partition_name = fname[:-3]
        log(f"\n处理: {fname} (分区: {partition_name})")
        log(f"  备份 → {backup_path.name}")

        rebuild_file(md_path, partition_name)

    log("\n" + "=" * 60)
    log("完成")
    log(f"备份位置: {backup_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
