# -*- coding: utf-8 -*-
"""BOSS直聘职位搜索采集

调用 opencli boss search 命令, 把搜索结果(职位/薪资/公司/地区/技能等)保存为 Obsidian Markdown。

用法:
    python boss_search.py                          # 弹窗输入关键词 + 城市 + 数量
    python boss_search.py "外贸"                    # 默认宁波, 采集 15 个
    python boss_search.py "外贸" 上海               # 指定城市
    python boss_search.py "外贸" 上海 30            # 指定城市 + 数量
    python boss_search.py "外贸" 上海 30 1-3年 本科  # 指定经验 + 学历
    python boss_search.py "外贸" 上海 30 不限 不限 9  # 断点续传: 从第 9 个开始获取详情
"""

import json
import os
import re
import sys
import time
import random
from datetime import datetime
from pathlib import Path

# 复用 xiaohongshu_collect 的工具函数 (OPENCLI_CMD / log / run_opencli 等)
sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OPENCLI_CMD,
    OBSIDIAN_ROOT,
    log,
    run_opencli,
    sanitize_filename,
)

# ============ 配置 ============
OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "BOSS直聘"
TIMEOUT_SEARCH = 150  # 搜索给足时间
TIMEOUT_DETAIL = 60   # 单个职位详情超时

# 防风控间隔 (秒): 详情请求之间随机等待
DETAIL_INTERVAL_MIN = 8
DETAIL_INTERVAL_MAX = 12
# 失败后重试: 最多重试次数 + 重试前等待秒数
DETAIL_RETRY_MAX = 2
DETAIL_RETRY_WAIT_MIN = 20
DETAIL_RETRY_WAIT_MAX = 30
# 连续失败后冷却 (秒)
DETAIL_COOLDOWN_FAILS = 2
DETAIL_COOLDOWN_WAIT_MIN = 60
DETAIL_COOLDOWN_WAIT_MAX = 120
# 批次暂停: 每 N 个职位暂停一次 (防止持续请求触发风控)
BATCH_SIZE = 5
BATCH_PAUSE_MIN = 45
BATCH_PAUSE_MAX = 90

# CLI 内部浏览器命令超时 (默认 60s 不够搜索, 提高到 120s)
os.environ.setdefault("OPENCLI_BROWSER_COMMAND_TIMEOUT", "120")

# 城市列表 (用于弹窗提示, 完整映射在 CLI 内部)
CITY_OPTIONS = [
    "全国", "北京", "上海", "广州", "深圳", "杭州", "成都", "南京",
    "武汉", "西安", "苏州", "长沙", "天津", "重庆", "郑州", "东莞",
    "青岛", "合肥", "佛山", "宁波", "厦门", "大连", "珠海", "无锡",
]

EXPERIENCE_OPTIONS = ["不限", "应届", "1年以内", "1-3年", "3-5年", "5-10年", "10年以上"]
DEGREE_OPTIONS = ["不限", "大专", "本科", "硕士", "博士"]
SALARY_OPTIONS = ["不限", "3K以下", "3-5K", "5-10K", "10-15K", "15-20K", "20-30K", "30-50K", "50K以上"]


def show_search_dialog():
    """tkinter 弹窗: 关键词 + 城市 + 数量 + 经验 + 学历"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return _parse_cli_args()

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    # 1. 关键词
    kw = simpledialog.askstring(
        "BOSS直聘搜索",
        "请输入搜索关键词:",
        initialvalue="外贸",
        parent=root,
    )
    if not kw or not kw.strip():
        root.destroy()
        return None, None, 0, "", ""
    kw = kw.strip()

    # 2. 城市
    city = simpledialog.askstring(
        "城市",
        f"城市名 (如 宁波/上海/杭州, 留空=宁波):",
        initialvalue="宁波",
        parent=root,
    )
    city = (city or "宁波").strip() or "宁波"

    # 3. 数量
    limit_str = simpledialog.askstring(
        "采集数量",
        f"搜索「{kw}」前几个职位? (1-100)",
        initialvalue="15",
        parent=root,
    )
    try:
        limit = max(1, min(100, int(limit_str)))
    except (TypeError, ValueError):
        limit = 15

    # 4. 经验 (可选)
    exp = simpledialog.askstring(
        "经验要求 (可选)",
        f"经验: {'/'.join(EXPERIENCE_OPTIONS)}",
        initialvalue="不限",
        parent=root,
    )
    exp = (exp or "不限").strip() or "不限"

    # 5. 学历 (可选)
    degree = simpledialog.askstring(
        "学历要求 (可选)",
        f"学历: {'/'.join(DEGREE_OPTIONS)}",
        initialvalue="不限",
        parent=root,
    )
    degree = (degree or "不限").strip() or "不限"

    root.destroy()
    return kw, city, limit, exp, degree


def _parse_cli_args():
    """无 tkinter 时从命令行参数解析"""
    if len(sys.argv) < 2:
        return None, None, 0, "", ""
    kw = sys.argv[1].strip()
    city = sys.argv[2].strip() if len(sys.argv) >= 3 else "北京"
    limit = 15
    if len(sys.argv) >= 4:
        try:
            limit = max(1, min(100, int(sys.argv[3])))
        except ValueError:
            pass
    exp = sys.argv[4].strip() if len(sys.argv) >= 5 else ""
    degree = sys.argv[5].strip() if len(sys.argv) >= 6 else ""
    return kw, city, limit, exp, degree


def search_jobs(query, city, limit, experience="", degree="", salary="", industry=""):
    """调用 opencli boss search

    返回: [{name, salary, company, area, experience, degree, skills, boss, url}, ...]
    """
    args = [
        "boss", "search", query,
        "--city", city,
        "--limit", str(limit),
        "-f", "json",
    ]
    if experience and experience != "不限":
        args.extend(["--experience", experience])
    if degree and degree != "不限":
        args.extend(["--degree", degree])
    if salary and salary != "不限":
        args.extend(["--salary", salary])
    if industry and industry != "不限":
        args.extend(["--industry", industry])

    filters = []
    if experience and experience != "不限":
        filters.append(f"经验={experience}")
    if degree and degree != "不限":
        filters.append(f"学历={degree}")
    if salary and salary != "不限":
        filters.append(f"薪资={salary}")
    filter_str = f" [{', '.join(filters)}]" if filters else ""

    log(f"调用 opencli boss search (城市={city}, limit={limit}){filter_str}")
    ok, stdout, err = run_opencli(args, TIMEOUT_SEARCH)
    if not ok:
        log(f"boss search 调用失败: {err}")
        return None

    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        log(f"意外的 JSON 结构: {type(data).__name__}")
        return None
    except json.JSONDecodeError as e:
        log(f"JSON 解析失败: {e}")
        log(f"原始 stdout 前 300 字符: {stdout[:300] if stdout else '(空)'}")
        return None


def get_job_detail(security_id):
    """调用 opencli boss detail 获取单个职位详情

    security_id: 来自 search 结果的 security_id 字段
    返回: dict 或 None
    """
    if not security_id:
        return None

    ok, stdout, err = run_opencli(
        ["boss", "detail", security_id, "-f", "json"],
        TIMEOUT_DETAIL,
    )
    if not ok:
        log(f"  detail 调用失败: {err}")
        return None

    try:
        data = json.loads(stdout)
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
        log(f"  detail 意外的 JSON 结构: {type(data).__name__}")
        return None
    except json.JSONDecodeError as e:
        log(f"  detail JSON 解析失败: {e}")
        return None


def update_frontmatter_status(md_content, status):
    """更新 Markdown 文件的 frontmatter 中的 status 字段"""
    # 替换现有的 status 行
    lines = md_content.split('\n')
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('status:'):
            lines[i] = f'status: {status}'
            updated = True
            break

    # 如果没有 status 行，在 frontmatter 结束前添加
    if not updated:
        for i, line in enumerate(lines):
            if line == '---' and i > 0:
                lines.insert(i, f'status: {status}')
                break

    return '\n'.join(lines)


def check_collection_complete(md_content, expected_count):
    """检查采集是否完整

    验证标准：
    1. 表格中有 expected_count 个职位
    2. 每个职位都有对应的详情区段（### N. 标题）

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
    is_complete = len(missing) == 0 and len(table_jobs) >= expected_count

    return is_complete, sorted(missing)


def build_markdown(query, city, jobs, details=None, experience="", degree="", status="采集中"):
    """生成 Obsidian markdown (汇总表格 + 职位详情)

    jobs: [{name, salary, company, area, experience, degree, skills, boss, security_id, url}, ...]
    details: {security_id: detail_dict, ...} 或 None
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_title = re.sub(r"[\r\n]+", " ", query)[:50]
    details = details or {}

    # 筛选条件描述
    filters = []
    if experience and experience != "不限":
        filters.append(f"经验={experience}")
    if degree and degree != "不限":
        filters.append(f"学历={degree}")
    filter_desc = f" | **筛选**: {', '.join(filters)}" if filters else ""

    lines = [
        "---",
        "tags: [BOSS直聘, 职位搜索]",
        f'title: "BOSS直聘搜索 - {safe_title}"',
        f'query: {json.dumps(query, ensure_ascii=False)}',
        f'city: "{city}"',
        'source: "BOSS直聘"',
        f"count: {len(jobs)}",
        f"createTime: {datetime.now().isoformat(timespec='seconds')}",
        f"status: {status}",
        "---",
        "",
        f"# BOSS直聘搜索 - {query}",
        "",
        f"> **关键词**: {query} | **城市**: {city} | **数量**: {len(jobs)} | **时间**: {now}{filter_desc}",
        "",
        "## 职位列表",
        "",
        "| # | 职位 | 薪资 | 公司 | 地区 | 经验 | 学历 | 职位描述 | securityId |",
        "|---|------|------|------|------|------|------|------|------|",
    ]

    for i, j in enumerate(jobs, 1):
        name = _clean_cell(j.get("name", "无标题"))
        salary = _clean_cell(j.get("salary", ""))
        company = _clean_cell(j.get("company", ""))
        area = _clean_cell(j.get("area", ""))
        exp = _clean_cell(j.get("experience", ""))
        deg = _clean_cell(j.get("degree", ""))
        url = j.get("url", "")

        # 职位名做成链接
        if url:
            name_cell = f"[{name}]({url})"
        else:
            name_cell = name

        # 职位描述列: Obsidian wikilink 跳转到详情区段 (管道符转义避免破坏表格)
        sid = j.get("security_id", "")
        has_detail = bool(details and details.get(sid))
        if has_detail:
            # 标题中的 | 替换为 - (与详情标题保持一致)
            safe_name = j.get("name", "").replace("|", "-")
            heading = f"{i}. {safe_name}"
            desc_cell = f"[[#{heading}\\|查看描述]]"
        else:
            desc_cell = ""

        # securityId 作为注释保存在表格中，续传时使用
        sid_comment = f"<!-- sid:{sid} -->" if sid else ""
        lines.append(f"| {i} | {name_cell} | {salary} | {company} | {area} | {exp} | {deg} | {desc_cell} | {sid_comment}")

    lines.append("")

    # 职位详情区段
    if details:
        lines.append("## 职位详情")
        lines.append("")
        for i, j in enumerate(jobs, 1):
            sid = j.get("security_id", "")
            detail = details.get(sid)
            if not detail:
                continue

            lines.extend(_build_detail_section(i, j, detail))
            lines.append("")

    return "\n".join(lines)


def _fix_list_format(line):
    """格式化描述行: 有序号转有序列表, 无序号非空行转无序列表"""
    stripped = line.strip()
    if not stripped:
        return ""
    # 有序号: 1.text / 1、text / 1. text / 1、 text → 1. text
    m = re.match(r'^(\d+)[.、]\s*(\S.*)', stripped)
    if m:
        return f"{m.group(1)}. {m.group(2)}"
    # 无序号: 添加无序列表前缀
    return f"- {stripped}"


def _build_detail_section(index, job, detail):
    """生成单个职位详情的 markdown 行列表 (公司信息 + 职位描述, 放入 Callout)"""
    name = job.get("name", "无标题")
    # 标题中替换 | 为 - (避免 Obsidian wikilink 解析冲突)
    safe_name = name.replace("|", "-")
    lines = [f"### {index}. {safe_name}", ""]

    # Callout 内容行
    callout_lines = []

    # 公司信息 (含行业/规模/融资阶段)
    company = detail.get("company", "") or job.get("company", "")
    industry = detail.get("industry", "")
    scale = detail.get("scale", "")
    stage = detail.get("stage", "")
    company_parts = []
    if company:
        company_parts.append(company)
    if industry:
        company_parts.append(industry)
    if scale:
        company_parts.append(scale)
    if stage:
        company_parts.append(stage)
    if company_parts:
        callout_lines.append(f"**公司**: {' · '.join(company_parts)}")

    # 职位描述
    description = detail.get("description", "")
    if description:
        callout_lines.append("")
        callout_lines.append("**职位描述**:")
        callout_lines.append("")
        for desc_line in description.split("\n"):
            callout_lines.append(_fix_list_format(desc_line))

    # 用 Callout 包裹
    lines.append("> [!info] 职位详情")
    for cl in callout_lines:
        lines.append(f"> {cl}" if cl else ">")

    return lines


def _clean_cell(val):
    """清洗表格单元格内容: 转义管道符, 替换换行"""
    if not val:
        return ""
    return str(val).replace("|", "\\|").replace("\n", " ").replace("\r", "")


def get_md_path(query, city):
    """确定 markdown 文件路径 (文件名冲突时加时间戳)"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(query)[:60] or "untitled"
    safe_city = sanitize_filename(city)[:20]
    md_path = OUTPUT_ROOT / f"{safe_name}_{safe_city}.md"
    if md_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        md_path = OUTPUT_ROOT / f"{safe_name}_{safe_city}_{ts}.md"
    return md_path


def write_markdown(md_path, md_content):
    """写入 markdown 到指定路径 (覆盖)"""
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def main():
    log("=" * 60)
    log("BOSS直聘职位搜索采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取搜索参数 (命令行参数优先, 无参数时弹窗)
    query = None
    city = "宁波"
    limit = 15
    experience = "不限"
    degree = "不限"
    start_index = 1  # 从第几个开始获取详情 (断点续传)
    if len(sys.argv) >= 2:
        query = sys.argv[1].strip()
        if len(sys.argv) >= 3:
            city = sys.argv[2].strip() or "宁波"
        if len(sys.argv) >= 4:
            try:
                limit = max(1, min(100, int(sys.argv[3])))
            except ValueError:
                pass
        if len(sys.argv) >= 5:
            experience = sys.argv[4].strip()
        if len(sys.argv) >= 6:
            degree = sys.argv[5].strip()
        # 第 7 个参数: --start-index=N 或直接数字
        if len(sys.argv) >= 7:
            arg7 = sys.argv[6].strip()
            if arg7.startswith("--start-index="):
                try:
                    start_index = max(1, int(arg7.split("=")[1]))
                except (ValueError, IndexError):
                    pass
            else:
                try:
                    start_index = max(1, int(arg7))
                except ValueError:
                    pass
    else:
        query, city, limit, experience, degree = show_search_dialog()

    if not query:
        log("未输入关键词, 退出")
        return 1

    log(f"关键词: {query}")
    log(f"城市: {city}")
    log(f"数量: {limit}")
    if experience:
        log(f"经验: {experience}")
    if degree:
        log(f"学历: {degree}")

    # 2. 调用 opencli boss search
    log("搜索中, 请稍候 (约 15-30 秒)...")
    jobs = search_jobs(query, city, limit, experience=experience, degree=degree)

    if not jobs:
        log("未获取到职位, 退出")
        return 2

    log(f"获取到 {len(jobs)} 个职位")

    # 2.5 过滤职位: 排除含"保洁"的职位
    excluded_keywords = ["保洁"]
    original_count = len(jobs)
    jobs = [j for j in jobs if not any(kw in j.get("name", "") for kw in excluded_keywords)]
    if len(jobs) < original_count:
        log(f"已过滤 {original_count - len(jobs)} 个含排除关键词的职位 ({', '.join(excluded_keywords)})")

    if not jobs:
        log("过滤后无职位, 退出")
        return 2

    # 3. 断点续传: 读取已有详情 (如果 start_index > 1)
    details = {}
    md_path = get_md_path(query, city)

    if start_index > 1 and md_path.exists():
        # 尝试从已有文件解析已获取的详情
        log(f"断点续传: 从第 {start_index} 个开始, 尝试读取已有详情...")
        try:
            import re
            existing_content = md_path.read_text(encoding="utf-8")
            # 从文件中提取已有的 security_id (通过表格中的链接匹配)
            # 简单方案: 检查详情区段是否存在
            detail_pattern = re.compile(r'^### (\d+)\. (.+)$', re.MULTILINE)
            existing_details = detail_pattern.findall(existing_content)
            if existing_details:
                log(f"已有 {len(existing_details)} 个详情, 将跳过这些职位")
        except Exception as e:
            log(f"读取已有文件失败: {e}, 将从头开始")

    # 写入初始文件 (如果不存在), 状态为"采集中"
    if not md_path.exists() or start_index == 1:
        md_content = build_markdown(query, city, jobs, details=details, experience=experience, degree=degree, status="采集中")
        write_markdown(md_path, md_content)
        log(f"已创建 (采集中): {md_path}")
    else:
        # 更新状态为"采集中"
        existing_content = md_path.read_text(encoding="utf-8")
        md_content = update_frontmatter_status(existing_content, "采集中")
        write_markdown(md_path, md_content)
        log(f"继续写入 (采集中): {md_path}")

    # 4. 逐个调用 boss detail, 每获取一个就更新文件
    if os.environ.get("SKIP_DETAIL") == "1":
        log("SKIP_DETAIL=1, 跳过详情获取")
        log(f"已保存: {md_path}")
        log("完成")
        return 0
    log(f"开始获取职位详情 ({len(jobs)} 个, 间隔 {DETAIL_INTERVAL_MIN}-{DETAIL_INTERVAL_MAX}秒, 重试{DETAIL_RETRY_MAX}次)...")
    if start_index > 1:
        log(f"断点续传: 从第 {start_index} 个开始")
    fail_count = 0
    consecutive_fails = 0
    for i, job in enumerate(jobs, 1):
        # 断点续传: 跳过已获取的职位
        if i < start_index:
            continue

        sid = job.get("security_id", "")
        if not sid:
            log(f"  [{i}/{len(jobs)}] {job.get('name', '?')[:30]} - 无 security_id, 跳过")
            continue

        log(f"  [{i}/{len(jobs)}] {job.get('name', '?')[:30]} - 获取详情...")

        # 防风控: 第 2 条起随机等待
        if i > 1:
            wait = random.uniform(DETAIL_INTERVAL_MIN, DETAIL_INTERVAL_MAX)
            time.sleep(wait)

        # 批次暂停: 每 N 个职位暂停一次 (让浏览器会话"休息")
        if i > 1 and (i - 1) % BATCH_SIZE == 0:
            wait = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
            log(f"  已完成 {i-1} 个, 批次暂停 {wait:.0f}秒...")
            time.sleep(wait)

        # 连续失败冷却: 达到阈值后长等待
        if consecutive_fails >= DETAIL_COOLDOWN_FAILS:
            wait = random.uniform(DETAIL_COOLDOWN_WAIT_MIN, DETAIL_COOLDOWN_WAIT_MAX)
            log(f"  连续失败 {consecutive_fails} 次, 冷却 {wait:.0f}秒...")
            time.sleep(wait)
            consecutive_fails = 0

        # 重试逻辑
        got_detail = None
        for attempt in range(1, DETAIL_RETRY_MAX + 2):  # 1次初试 + N次重试
            try:
                got_detail = get_job_detail(sid)
                if got_detail:
                    break
            except Exception as e:
                log(f"  [{i}/{len(jobs)}] 第{attempt}次异常: {e}")
                got_detail = None

            if attempt <= DETAIL_RETRY_MAX:
                wait = random.uniform(DETAIL_RETRY_WAIT_MIN, DETAIL_RETRY_WAIT_MAX)
                log(f"  [{i}/{len(jobs)}] 第{attempt}次失败, {wait:.0f}秒后重试...")
                time.sleep(wait)

        if got_detail:
            details[sid] = got_detail
            log(f"  [{i}/{len(jobs)}] OK")
            consecutive_fails = 0
        else:
            fail_count += 1
            consecutive_fails += 1
            log(f"  [{i}/{len(jobs)}] 失败 (重试{DETAIL_RETRY_MAX}次仍失败)")

        # 每次获取后立即更新文件 (覆盖同一文件, 中断也能保留已获取的详情)
        md_content = build_markdown(query, city, jobs, details=details, experience=experience, degree=degree)
        write_markdown(md_path, md_content)

    # 验证采集完整性并更新状态
    md_content = md_path.read_text(encoding="utf-8")
    is_complete, missing_indexes = check_collection_complete(md_content, len(jobs))

    if is_complete:
        md_content = update_frontmatter_status(md_content, "已采集")
        write_markdown(md_path, md_content)
        log(f"详情获取完成: 成功 {len(details)}/{len(jobs)}, 失败 {fail_count}")
        log(f"已保存 (已采集): {md_path}")
    else:
        log(f"详情获取完成: 成功 {len(details)}/{len(jobs)}, 失败 {fail_count}")
        log(f"缺失详情: {missing_indexes}")
        log(f"已保存 (采集中): {md_path} - 需要补充 {len(missing_indexes)} 个详情")

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
