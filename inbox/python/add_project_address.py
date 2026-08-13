# -*- coding: utf-8 -*-
"""为 IT咖啡馆笔记批量追加视频简介/项目地址模块

扫描 d:/obsidian/视频/resource/ 下的 IT咖啡馆*.md 文件,
对没有 ## 项目地址 / ## 视频简介 模块的笔记,
调用 opencli bilibili video 获取 desc, 格式化后追加到末尾。

- desc 含 "GitHub链接"/"项目名称" → 追加为 ## 项目地址 (多行)
- desc 为普通简介 → 追加为 ## 视频简介

支持断点续传: 已处理文件路径记录在 _processed.txt 中。
用法:
    python add_project_address.py
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import log, run_opencli  # noqa: E402

# ============ 配置 ============
RESOURCE_DIR = Path("d:/obsidian/视频/resource")
TIMEOUT_VIDEO = 60
LOG_DIR = Path("d:/obsidian/demo/05_long_project/程序运行日志")
PROCESSED_LOG = LOG_DIR / "add_project_address_processed.txt"

# 已存在模块的标题 (检测时跳过)
EXISTING_SECTIONS = ("项目地址", "视频简介")


def extract_bvid(content):
    """从 frontmatter 提取 BV 号

    frontmatter 格式: 作品网址: "https://www.bilibili.com/video/BV1xxx"
    或: 作品网址: https://www.bilibili.com/video/BV1xxx
    """
    m = re.search(r'作品网址:\s*"?https?://www\.bilibili\.com/video/(BV[\w]+)', content)
    return m.group(1) if m else None


def has_existing_section(content):
    """检查是否已有 ## 项目地址 或 ## 视频简介 模块"""
    for section in EXISTING_SECTIONS:
        if re.search(rf'^##\s+{re.escape(section)}', content, re.MULTILINE):
            return True
    return False


def fetch_desc(bvid):
    """调用 opencli bilibili video 获取 desc

    返回: (desc, error)  desc 为 None 时表示失败
    """
    args = ["bilibili", "video", bvid, "--format", "md"]
    ok, stdout, err = run_opencli(args, TIMEOUT_VIDEO)
    if not ok:
        return None, err or "opencli call failed"
    # 解析 markdown 表格: | bvid | title | ... | desc |
    for line in stdout.split("\n"):
        if line.startswith("| BV") or "| BV" in line[:5]:
            fields = [f.strip() for f in line.split("|") if f.strip()]
            # 字段顺序: bvid, title, author, plays, likes, coins, favorites, shares, date, desc
            if len(fields) >= 10:
                return fields[9], None
    return None, "desc not found in table output"


def format_desc(desc):
    """格式化 desc

    - 项目地址格式: 将 '1、... 2、...' 拆分为多行
    - 普通简介: 保持原样
    """
    # 在 "数字、" 前插入换行 (不在字符串开头)
    formatted = re.sub(r'(?<!^)\s*(\d+、)', r'\n\1', desc)
    return formatted


def is_project_address(desc):
    """判断 desc 是否为项目地址格式"""
    keywords = ["GitHub链接", "github链接", "项目名称", "GitHub 链接"]
    return any(kw in desc for kw in keywords)


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 收集待处理文件
    all_files = sorted(RESOURCE_DIR.glob("IT咖啡馆*.md"))
    need_process = []
    for f in all_files:
        try:
            content = f.read_text(encoding="utf-8")
        except Exception as e:
            log(f"读取失败 {f.name}: {e}")
            continue
        if not has_existing_section(content):
            need_process.append(f)

    log(f"总文件数: {len(all_files)}")
    log(f"待处理: {len(need_process)}")

    if not need_process:
        log("没有需要处理的文件")
        return

    # 断点续传: 读取已处理文件
    processed = set()
    if PROCESSED_LOG.exists():
        processed = set(
            line.strip()
            for line in PROCESSED_LOG.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    log(f"已处理(将跳过): {len(processed)}")

    success = 0
    fail = 0
    skip = 0
    failed_files = []

    for i, f in enumerate(need_process, 1):
        if str(f) in processed:
            skip += 1
            continue

        log(f"[{i}/{len(need_process)}] {f.name}")

        try:
            content = f.read_text(encoding="utf-8")
        except Exception as e:
            log(f"  读取失败: {e}")
            fail += 1
            failed_files.append(f.name)
            continue

        bvid = extract_bvid(content)
        if not bvid:
            log(f"  无法提取 BV 号, 跳过")
            fail += 1
            failed_files.append(f.name)
            continue

        log(f"  BV: {bvid}")

        # 调用 opencli, 最多重试 3 次
        desc = None
        last_err = ""
        for attempt in range(3):
            desc, err = fetch_desc(bvid)
            if desc:
                break
            last_err = err or "unknown"
            log(f"  尝试 {attempt + 1}/3 失败: {str(last_err)[:80]}")
            if attempt < 2:
                time.sleep(2)

        if not desc:
            log(f"  获取 desc 失败, 跳过")
            fail += 1
            failed_files.append(f.name)
            continue

        # 格式化并追加
        formatted = format_desc(desc)
        is_addr = is_project_address(desc)
        section_title = "项目地址" if is_addr else "视频简介"
        section = f"\n## {section_title}\n{formatted}\n"

        # 确保原文件末尾有换行
        if not content.endswith("\n"):
            content += "\n"

        try:
            f.write_text(content + section, encoding="utf-8")
            log(f"  成功追加 ## {section_title}")
            success += 1
        except Exception as e:
            log(f"  写入失败: {e}")
            fail += 1
            failed_files.append(f.name)
            continue

        # 记录已处理
        try:
            with open(PROCESSED_LOG, "a", encoding="utf-8") as pf:
                pf.write(str(f) + "\n")
        except Exception:
            pass

        # 请求间隔, 避免风控
        time.sleep(0.5)

    log("")
    log(f"========== 完成 ==========")
    log(f"成功: {success}")
    log(f"失败: {fail}")
    log(f"跳过(已处理): {skip}")
    if failed_files:
        log("失败文件:")
        for name in failed_files:
            log(f"  - {name}")


if __name__ == "__main__":
    main()
