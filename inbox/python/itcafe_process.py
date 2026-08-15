# -*- coding: utf-8 -*-
"""视频笔记处理: 追加视频简介 + 修复二级标题格式 (IT咖啡馆)

功能:
1. 对没有 ## 项目地址 / ## 视频简介 模块的笔记,
   调用 opencli bilibili video 获取 desc, 格式化后追加到末尾。
   - desc 含 "GitHub链接"/"项目名称" → 追加为 ## 项目地址 (多行)
   - desc 为普通简介 → 追加为 ## 视频简介
   支持按修改时间过滤: 只处理指定时间之后的笔记。

2. 修复二级标题误用 (仅 IT咖啡馆 笔记):
   - `## - xxx` → `- xxx` (二级标题误用为列表项)
   - `* ## xxx` / `- ## xxx` → `* xxx` / `- xxx` (列表项中嵌套二级标题)
   - `## xxx` → `- xxx` (二级标题误用为内容)
   跳过合法标题: ## 项目地址, ## 视频简介

支持断点续传: 已处理文件路径记录在 _processed.txt 中。
用法:
    python itcafe_process.py                    # 处理所有笔记
    python itcafe_process.py "2026-08-14 10:37" # 只处理该时间之后的笔记
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import log, run_opencli  # noqa: E402

# ============ 配置 ============
RESOURCE_DIR = Path("d:/obsidian/视频/resource")
TIMEOUT_VIDEO = 60
LOG_DIR = Path("d:/obsidian/demo/05_long_project/程序运行日志")
PROCESSED_LOG = LOG_DIR / "itcafe_process_processed.txt"

# 合法的二级标题 (章节标题, 不应转换为列表项)
VALID_HEADINGS = {"项目地址", "视频简介"}

# 已存在模块的标题 (检测时跳过追加)
EXISTING_SECTIONS = ("项目地址", "视频简介")

# 匹配三种二级标题误用:
BAD_HEADING_PATTERN_1 = re.compile(r"^##\s+-\s+(.*)$")
BAD_HEADING_PATTERN_2 = re.compile(r"^([*\-])\s+##\s+(.*)$")
BAD_HEADING_PATTERN_3 = re.compile(r"^##\s+(.*)$")


# ============ 追加视频简介 ============

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
    使用 JSON 格式以正确处理 desc 中的换行符
    """
    args = ["bilibili", "video", bvid, "--format", "json"]
    ok, stdout, err = run_opencli(args, TIMEOUT_VIDEO)
    if not ok:
        return None, err or "opencli call failed"
    try:
        data = json.loads(stdout)
        if isinstance(data, list) and len(data) > 0:
            desc = data[0].get("desc", "") or ""
            return (desc if desc else None), None
        return None, "no data in json output"
    except json.JSONDecodeError as e:
        return None, f"json parse error: {e}"


def format_desc(desc):
    """格式化 desc: 将 '1、... 2、...' 拆分为多行"""
    formatted = re.sub(r'(?<!^)\s*(\d+、)', r'\n\1', desc)
    return formatted


def is_project_address(desc):
    """判断 desc 是否为项目地址格式"""
    keywords = ["GitHub链接", "github链接", "项目名称", "GitHub 链接"]
    return any(kw in desc for kw in keywords)


def append_sections(need_process, processed):
    """追加视频简介/项目地址模块

    返回: (success, fail, skip, failed_files, new_processed)
    """
    success = 0
    fail = 0
    skip = 0
    failed_files = []
    new_processed = set()

    for i, f in enumerate(need_process, 1):
        if str(f) in processed:
            skip += 1
            continue

        log(f"[{i}/{len(need_process)}] 追加模块: {f.name}")

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
            new_processed.add(str(f))
        except Exception as e:
            log(f"  写入失败: {e}")
            fail += 1
            failed_files.append(f.name)
            continue

        # 请求间隔, 避免风控
        time.sleep(0.5)

    return success, fail, skip, failed_files, new_processed


# ============ 修复二级标题格式 ============

def fix_content(content, apply_pattern3=False):
    """修复二级标题误用

    1. `## - xxx` → `- xxx` (二级标题误用为列表项, 所有笔记)
    2. `* ## xxx` / `- ## xxx` → `* xxx` / `- xxx` (列表项中嵌套二级标题, 所有笔记)
    3. `## xxx` → `- xxx` (二级标题误用为内容, 仅 apply_pattern3=True 时处理)
    4. 删除该行前面的空行, 让列表连续
    5. 跳过合法标题: ## 项目地址, ## 视频简介
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
        # 跳过合法的二级标题 (如 ## 项目地址, ## 视频简介)
        if m3 and m3.group(1).strip() in VALID_HEADINGS:
            new_lines.append(line)
            continue
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
        elif m3 and apply_pattern3:
            # `## xxx` → `- xxx` (仅 IT咖啡馆 等指定文件)
            new_line = f"- {m3.group(1)}"
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            new_lines.append(new_line)
            fixed_count += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines), fixed_count


def fix_format(all_files):
    """修复笔记的二级标题格式

    IT咖啡馆 笔记: 应用全部三种模式
    其他笔记: 仅应用模式1和模式2 (避免误伤合法章节标题)

    返回: (affected_files, total_fixed)
    """
    affected_files = 0
    total_fixed = 0

    for md_path in all_files:
        # IT咖啡馆 笔记应用全部三种模式, 其他笔记仅模式1和2
        is_itcafe = md_path.name.startswith("IT咖啡馆")
        try:
            content = md_path.read_text(encoding="utf-8")
            new_content, fixed_count = fix_content(content, apply_pattern3=is_itcafe)

            if fixed_count > 0:
                md_path.write_text(new_content, encoding="utf-8")
                log(f"  修复格式: {md_path.name}: {fixed_count} 处")
                total_fixed += fixed_count
                affected_files += 1
        except Exception as e:
            log(f"  修复失败: {md_path.name}: {str(e)[:60]}")

    return affected_files, total_fixed


# ============ 主流程 ============

def main():
    # 解析时间过滤参数
    since_time = None
    if len(sys.argv) > 1:
        try:
            since_time = datetime.strptime(sys.argv[1], "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                since_time = datetime.strptime(sys.argv[1], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                log(f"无法解析时间参数: {sys.argv[1]}, 格式: 'YYYY-MM-DD HH:MM'")
                return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ===== 第一步: 追加视频简介/项目地址模块 (所有笔记) =====
    log("========== 第一步: 追加视频简介/项目地址 ==========")

    if since_time:
        log(f"时间过滤: {since_time.strftime('%Y-%m-%d %H:%M')} 之后")

    # 处理所有 *.md 文件 (不只是 IT咖啡馆)
    all_md_files = sorted(RESOURCE_DIR.glob("*.md"))
    if since_time:
        all_md_files = [f for f in all_md_files if datetime.fromtimestamp(f.stat().st_mtime) >= since_time]

    need_process = []
    for f in all_md_files:
        try:
            content = f.read_text(encoding="utf-8")
        except Exception as e:
            log(f"读取失败 {f.name}: {e}")
            continue
        if not has_existing_section(content):
            need_process.append(f)

    log(f"扫描文件数: {len(all_md_files)}")
    log(f"待追加: {len(need_process)}")

    # 断点续传: 读取已处理文件
    processed = set()
    if PROCESSED_LOG.exists():
        processed = set(
            line.strip()
            for line in PROCESSED_LOG.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    log(f"已处理(将跳过): {len(processed)}")

    success, fail, skip, failed_files, new_processed = append_sections(
        need_process, processed
    )

    # 更新断点续传记录
    if new_processed:
        processed.update(new_processed)
        try:
            with open(PROCESSED_LOG, "w", encoding="utf-8") as pf:
                for p in processed:
                    pf.write(p + "\n")
        except Exception:
            pass

    log("")
    log(f"追加结果: 成功 {success}, 失败 {fail}, 跳过 {skip}")
    if failed_files:
        log("失败文件:")
        for name in failed_files:
            log(f"  - {name}")

    # ===== 第二步: 修复二级标题格式 (所有笔记) =====
    log("")
    log("========== 第二步: 修复二级标题格式 ==========")
    # 模式1,2 对所有笔记; 模式3 仅对 IT咖啡馆
    fix_files = sorted(RESOURCE_DIR.glob("*.md"))
    if since_time:
        fix_files = [f for f in fix_files if datetime.fromtimestamp(f.stat().st_mtime) >= since_time]
    log(f"扫描文件数: {len(fix_files)}")

    affected_files, total_fixed = fix_format(fix_files)

    log("")
    log(f"修复结果: 影响文件 {affected_files} 个, 总修复 {total_fixed} 处")
    log("")
    log("========== 全部完成 ==========")


if __name__ == "__main__":
    main()
