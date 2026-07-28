# -*- coding: utf-8 -*-
"""BOSS直聘详情续传

从已有 Markdown 文件中提取未获取详情的职位 URL, 调用 boss detail 补充完整。
避免重新搜索导致结果不一致。

用法:
    python boss_resume.py                              # 自动扫描 BOSS直聘 目录下未完成的文件
    python boss_resume.py "布童科技_宁波.md"           # 指定文件
    python boss_resume.py "布童科技_宁波.md" 8         # 从第 8 个开始补充
"""

import json
import os
import re
import sys
import time
import random
import base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import OPENCLI_CMD, log, run_opencli, OBSIDIAN_ROOT

# ============ 配置 ============
DETAIL_INTERVAL_MIN = 8
DETAIL_INTERVAL_MAX = 12
DETAIL_RETRY_MAX = 2
DETAIL_RETRY_WAIT_MIN = 20
DETAIL_RETRY_WAIT_MAX = 30
# 连续失败后冷却 (秒)
DETAIL_COOLDOWN_FAILS = 2
DETAIL_COOLDOWN_WAIT_MIN = 60
DETAIL_COOLDOWN_WAIT_MAX = 120
# 批次暂停: 每 N 个职位暂停一次
BATCH_SIZE = 5
BATCH_PAUSE_MIN = 15
BATCH_PAUSE_MAX = 25

OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "BOSS直聘"


def _sleep_with_heartbeat(seconds, label="暂停"):
    """带心跳日志的 sleep: 每 10 秒输出一次心跳, 防止父进程误判卡死而杀掉脚本"""
    elapsed = 0
    total = int(seconds)
    while elapsed < total:
        chunk = min(10, total - elapsed)
        time.sleep(chunk)
        elapsed += chunk
        if elapsed < total:
            log(f"  {label}中... ({elapsed}/{total}秒)")


def _decode_sid(stored):
    """解码 securityId: 支持 b64: 前缀 (新格式) 和原始值 (旧格式兼容)"""
    if not stored:
        return ""
    if stored.startswith("b64:"):
        try:
            return base64.b64decode(stored[4:]).decode("utf-8")
        except Exception:
            return stored  # 解码失败, 返回原始值
    return stored


def parse_frontmatter_status(md_content):
    """解析 Markdown 文件的 frontmatter 中的 status 字段"""
    match = re.search(r'^status:\s*(.+)$', md_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def check_collection_complete(md_content):
    """检查采集是否完整

    验证标准：
    1. 表格中的每个职位都有对应的详情区段

    返回: (is_complete, missing_indexes)
    """
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

    return is_complete, sorted(missing)


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

def parse_table_jobs(md_content):
    """从 Markdown 文件解析表格中的职位列表

    返回: [(index, name, url, security_id), ...]
    """
    jobs = []
    # 匹配表格行: | 1 | [职位名](URL) | ... | <!-- sid:xxx --> |
    # 或者旧格式: | 1 | [职位名](URL) | ... |
    pattern = re.compile(r'^\| (\d+) \| \[([^\]]+)\]\(([^)]+)\) \|.*?(?:<!-- sid:([^>]+) -->)?\s*$', re.MULTILINE)
    for m in pattern.finditer(md_content):
        index = int(m.group(1))
        name = m.group(2)
        url = m.group(3)
        security_id = _decode_sid(m.group(4)) if m.group(4) else ""
        jobs.append((index, name, url, security_id))
    return jobs

def parse_existing_details(md_content):
    """从 Markdown 文件解析已有的详情区段

    返回: set of indexes (已获取详情的职位编号)
    """
    existing = set()
    # 匹配详情标题: ### 1. 职位名
    pattern = re.compile(r'^### (\d+)\. ', re.MULTILINE)
    for m in pattern.finditer(md_content):
        existing.add(int(m.group(1)))
    return existing

def get_job_detail(security_id):
    """调用 opencli boss detail 获取单个职位详情"""
    args = ["boss", "detail", "-f", "json", "--", security_id]
    ok, stdout, err = run_opencli(args, 60)
    if not ok:
        log(f"  detail 调用失败: {(err or 'unknown')[:200]}")
        return None
    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            return data[0]
        log(f"  detail 意外 JSON: {type(data).__name__}")
        return None
    except json.JSONDecodeError as e:
        log(f"  detail JSON 解析失败: {e}, stdout={stdout[:200] if stdout else '(空)'}")
        return None

def build_detail_section(index, name, detail):
    """生成单个职位详情的 markdown"""
    # 标题中替换 | 为 -
    safe_name = name.replace("|", "-")
    lines = [f"### {index}. {safe_name}", ""]

    callout_lines = []

    # 公司信息
    company = detail.get("company", "")
    industry = detail.get("industry", "")
    scale = detail.get("scale", "")
    stage = detail.get("stage", "")
    company_parts = [p for p in [company, industry, scale, stage] if p]
    if company_parts:
        callout_lines.append(f"**公司**: {' · '.join(company_parts)}")

    # 职位描述
    description = detail.get("description", "")
    if description:
        callout_lines.append("")
        callout_lines.append("**职位描述**:")
        callout_lines.append("")
        for desc_line in description.split("\n"):
            stripped = desc_line.strip()
            if not stripped:
                callout_lines.append("")
                continue
            # 有序号转有序列表, 无序号转无序列表
            m = re.match(r'^(\d+)[.、]\s*(\S.*)', stripped)
            if m:
                callout_lines.append(f"{m.group(1)}. {m.group(2)}")
            else:
                callout_lines.append(f"- {stripped}")

    lines.append("> [!info] 职位详情")
    for cl in callout_lines:
        lines.append(f"> {cl}" if cl else ">")

    return "\n".join(lines)

def main():
    # 如果没有参数, 扫描 BOSS直聘 目录下未完成的文件
    if len(sys.argv) < 2:
        return scan_and_resume_all()

    file_path_arg = sys.argv[1]

    # 如果是目录路径, 扫描该目录
    if file_path_arg.endswith('/') or file_path_arg.endswith('\\'):
        dir_path = Path(file_path_arg)
    elif Path(file_path_arg).is_dir():
        dir_path = Path(file_path_arg)
    else:
        # 单个文件模式
        file_path = Path(file_path_arg)
        if not file_path.is_absolute():
            file_path = OUTPUT_ROOT / file_path

        if not file_path.exists():
            print(f"文件不存在: {file_path}")
            return 1

        start_index = 1
        if len(sys.argv) >= 3:
            try:
                start_index = max(1, int(sys.argv[2]))
            except ValueError:
                pass

        return resume_single_file(file_path, start_index)


def scan_and_resume_all():
    """扫描 BOSS直聘 目录下所有未完成的文件"""
    log("=" * 60)
    log("BOSS直聘详情续传 - 批量扫描")
    log(f"目录: {OUTPUT_ROOT}")
    log("=" * 60)

    if not OUTPUT_ROOT.exists():
        log("目录不存在")
        return 1

    # 查找所有 .md 文件
    md_files = list(OUTPUT_ROOT.glob("*.md"))
    if not md_files:
        log("未找到 Markdown 文件")
        return 0

    log(f"共找到 {len(md_files)} 个文件")

    # 筛选状态不为"已采集"的文件
    incomplete_files = []
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
            status = parse_frontmatter_status(content)
            if status != "已采集":
                incomplete_files.append((md_file, status or "无状态"))
        except Exception as e:
            log(f"读取 {md_file.name} 失败: {e}")

    if not incomplete_files:
        log("所有文件状态均为'已采集', 无需补充")
        return 0

    log(f"发现 {len(incomplete_files)} 个未完成的文件:")
    for md_file, status in incomplete_files:
        log(f"  - {md_file.name} (状态: {status})")

    # 逐个处理
    total_success = 0
    for idx, (md_file, status) in enumerate(incomplete_files, 1):
        log("")
        log(f"[{idx}/{len(incomplete_files)}] 处理: {md_file.name}")
        result = resume_single_file(md_file, 1)
        if result == 0:
            total_success += 1

    log("")
    log("=" * 60)
    log(f"批量续传完成: 成功 {total_success}/{len(incomplete_files)}")
    log("=" * 60)
    return 0


def _append_detail_to_file(file_path, index, name, detail):
    """将单个职位详情追加到 Markdown 文件 (增量写入)

    每次成功获取详情后立即调用, 确保脚本被杀时已获取的详情不丢失。
    """
    md_content = file_path.read_text(encoding="utf-8")

    # 确保有 "## 职位详情" 区段
    if "## 职位详情" not in md_content:
        md_content = md_content.rstrip() + "\n\n## 职位详情\n\n"

    # 检查是否已存在
    if f"### {index}. " in md_content:
        return  # 已存在, 跳过

    detail_md = build_detail_section(index, name, detail)
    md_content = md_content.rstrip() + "\n\n" + detail_md + "\n"
    file_path.write_text(md_content, encoding="utf-8")


def resume_single_file(file_path, start_index=1):
    """处理单个文件的续传"""
    log("=" * 60)
    log("BOSS直聘详情续传 启动")
    log(f"文件: {file_path}")
    log(f"起始编号: {start_index}")
    log("=" * 60)

    # 1. 解析文件
    md_content = file_path.read_text(encoding="utf-8")
    all_jobs = parse_table_jobs(md_content)
    existing_details = parse_existing_details(md_content)

    log(f"表格中共 {len(all_jobs)} 个职位")
    log(f"已获取 {len(existing_details)} 个详情: {sorted(existing_details)}")

    # 2. 找出缺失的详情
    missing_jobs = [(i, n, u, s) for i, n, u, s in all_jobs if i >= start_index and i not in existing_details]

    if not missing_jobs:
        log("无需补充, 所有详情已完整")
        return 0

    log(f"需要补充 {len(missing_jobs)} 个详情: {[i for i, n, u, s in missing_jobs]}")

    # 3. 逐个获取详情 (每获取一个就立即写入文件, 防止脚本被杀时丢失)
    success_count = 0
    fail_count = 0
    consecutive_fails = 0

    for idx, (i, name, url, sid) in enumerate(missing_jobs, 1):
        if not sid:
            log(f"  [{idx}/{len(missing_jobs)}] #{i} - 无 securityId, 跳过")
            continue

        log(f"  [{idx}/{len(missing_jobs)}] #{i} {name[:30]} - 获取详情...")

        # 防风控等待
        if idx > 1:
            wait = random.uniform(DETAIL_INTERVAL_MIN, DETAIL_INTERVAL_MAX)
            time.sleep(wait)

        # 批次暂停: 每 N 个职位暂停一次
        if idx > 1 and (idx - 1) % BATCH_SIZE == 0:
            wait = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
            log(f"  已完成 {idx-1} 个, 批次暂停 {wait:.0f}秒...")
            _sleep_with_heartbeat(wait, "批次暂停")

        # 连续失败冷却: 达到阈值后长等待
        if consecutive_fails >= DETAIL_COOLDOWN_FAILS:
            wait = random.uniform(DETAIL_COOLDOWN_WAIT_MIN, DETAIL_COOLDOWN_WAIT_MAX)
            log(f"  连续失败 {consecutive_fails} 次, 冷却 {wait:.0f}秒...")
            _sleep_with_heartbeat(wait, "冷却")
            consecutive_fails = 0

        # 重试逻辑
        got_detail = None
        for attempt in range(1, DETAIL_RETRY_MAX + 2):
            try:
                got_detail = get_job_detail(sid)
                if got_detail:
                    break
            except Exception as e:
                log(f"  [{idx}/{len(missing_jobs)}] 第{attempt}次异常: {e}")

            if attempt <= DETAIL_RETRY_MAX:
                wait = random.uniform(DETAIL_RETRY_WAIT_MIN, DETAIL_RETRY_WAIT_MAX)
                log(f"  [{idx}/{len(missing_jobs)}] 第{attempt}次失败, {wait:.0f}秒后重试...")
                _sleep_with_heartbeat(wait, "重试等待")

        if got_detail:
            # 增量写入: 立即保存到文件, 防止脚本被杀时丢失
            _append_detail_to_file(file_path, i, name, got_detail)
            success_count += 1
            consecutive_fails = 0
            log(f"  [{idx}/{len(missing_jobs)}] OK (已保存)")
        else:
            fail_count += 1
            consecutive_fails += 1
            log(f"  [{idx}/{len(missing_jobs)}] 失败 (重试{DETAIL_RETRY_MAX}次仍失败)")

    log(f"详情获取完成: 成功 {success_count}/{len(missing_jobs)}, 失败 {fail_count}")

    if fail_count == len(missing_jobs):
        log("")
        log("⚠️  所有详情获取都失败！可能原因：")
        log("  1. securityId 已过期（有时效性）")
        log("  2. 需要重新搜索获取最新的 securityId")
        log("  3. 浏览器cookie可能已过期")
        log("")
        log("建议：运行 boss_search.py 重新采集，而不是续传")

    # 4. 验证采集完整性并更新状态
    md_content = file_path.read_text(encoding="utf-8")
    is_complete, missing_after = check_collection_complete(md_content)
    if is_complete:
        md_content = update_frontmatter_status(md_content, "已采集")
        file_path.write_text(md_content, encoding="utf-8")
        log(f"已更新 (已采集): {file_path}")
    else:
        log(f"已更新 (采集中): {file_path} - 仍缺失 {len(missing_after)} 个详情: {missing_after}")

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