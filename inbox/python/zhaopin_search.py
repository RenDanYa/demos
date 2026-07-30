# -*- coding: utf-8 -*-
"""智联招聘职位搜索采集

调用 opencli zhaopin search/detail 命令, 把搜索结果(职位/薪资/公司/地区/经验/学历等)保存为 Obsidian Markdown。

用法:
    python zhaopin_search.py                          # 弹窗输入关键词 + 城市 + 数量
    python zhaopin_search.py "外贸"                    # 默认宁波, 采集 20 个
    python zhaopin_search.py "外贸" 上海               # 指定城市
    python zhaopin_search.py "外贸" 上海 30            # 指定城市 + 数量
    python zhaopin_search.py "外贸" 上海 30 5          # 断点续传: 从第 5 个开始获取详情
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
SOURCE = "智联招聘"
OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "招聘"
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
BATCH_PAUSE_MIN = 15
BATCH_PAUSE_MAX = 25

# 智联招聘城市列表 (用于弹窗提示, 完整映射在 CLI 内部)
CITY_OPTIONS = [
    "全国", "北京", "上海", "广州", "深圳", "杭州", "成都", "南京",
    "武汉", "西安", "苏州", "厦门", "宁波",
]

# CLI 内部浏览器命令超时
os.environ.setdefault("OPENCLI_BROWSER_COMMAND_TIMEOUT", "120")


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


def show_search_dialog():
    """tkinter 弹窗: 关键词 + 城市 + 数量"""
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
        "智联招聘搜索",
        "请输入搜索关键词:",
        initialvalue="外贸",
        parent=root,
    )
    if not kw or not kw.strip():
        root.destroy()
        return None, None, 0
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
        initialvalue="20",
        parent=root,
    )
    try:
        limit = max(1, min(100, int(limit_str)))
    except (TypeError, ValueError):
        limit = 20

    root.destroy()
    return kw, city, limit


def _parse_cli_args():
    """无 tkinter 时从命令行参数解析"""
    if len(sys.argv) < 2:
        return None, None, 0
    kw = sys.argv[1].strip()
    city = sys.argv[2].strip() if len(sys.argv) >= 3 else "宁波"
    limit = 20
    if len(sys.argv) >= 4:
        try:
            limit = max(1, min(100, int(sys.argv[3])))
        except ValueError:
            pass
    return kw, city, limit


def _extract_job_id(url):
    """从智联招聘 URL 中提取职位 ID

    如 http://www.zhaopin.com/jobdetail/CC363256114J00174549604.htm?... → CC363256114J00174549604
    """
    if not url:
        return ""
    m = re.search(r'/jobdetail/([A-Za-z0-9]+)', url)
    if m:
        return m.group(1)
    return url


def search_jobs(query, city, limit):
    """调用 opencli zhaopin search

    返回: [{rank, title, salary, company, location, experience, education, tags, url}, ...]
    """
    args = [
        "zhaopin", "search", query,
        "--city", city,
        "--limit", str(limit),
        "-f", "json",
    ]

    log(f"调用 opencli zhaopin search (城市={city}, limit={limit})")
    ok, stdout, err = run_opencli(args, TIMEOUT_SEARCH)
    if not ok:
        log(f"zhaopin search 调用失败: {err}")
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


def get_job_detail(job_url):
    """调用 opencli zhaopin detail 获取单个职位详情

    job_url: 职位详情页 URL 或职位 ID
    返回: dict 或 None
    """
    if not job_url:
        return None

    # 提取职位 ID (避免 URL 中的查询参数干扰 CLI 解析)
    job_id = _extract_job_id(job_url) or job_url

    ok, stdout, err = run_opencli(
        ["zhaopin", "detail", "-f", "json", "--", job_id],
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


def check_collection_complete(md_content, expected_count):
    """检查采集是否完整

    验证标准:
    1. 表格中有 expected_count 个职位
    2. 每个职位都有对应的详情区段 (### N. 标题)
    """
    table_jobs = set()
    table_pattern = re.compile(r'^\| (\d+) \|', re.MULTILINE)
    for m in table_pattern.finditer(md_content):
        table_jobs.add(int(m.group(1)))

    detail_jobs = set()
    detail_pattern = re.compile(r'^### (\d+)\. ', re.MULTILINE)
    for m in detail_pattern.finditer(md_content):
        detail_jobs.add(int(m.group(1)))

    missing = table_jobs - detail_jobs
    is_complete = len(missing) == 0 and len(table_jobs) >= expected_count

    return is_complete, sorted(missing)


def _clean_cell(val):
    """清洗表格单元格内容: 转义管道符, 替换换行"""
    if not val:
        return ""
    return str(val).replace("|", "\\|").replace("\n", " ").replace("\r", "")


def _fix_list_format(line):
    """格式化描述行: 统一转为无序列表行 (去除行首序号)"""
    stripped = line.strip()
    if not stripped:
        return ""
    # 去除行首序号 (1. / 1、 等) 后统一加无序列表前缀
    m = re.match(r'^(\d+)[.、]\s*(\S.*)', stripped)
    if m:
        return f"- {m.group(2)}"
    return f"- {stripped}"


def _split_description(text):
    """将职位描述文本拆分为行列表

    处理两种情况:
    1. 正常换行的文本 — 直接按 \\n 分割
    2. 无换行但含中文编号的段落 (如 "1、xxx2、xxx3、xxx") — 在编号前插入换行再分割
    """
    if not text:
        return []

    # 如果文本本身有换行, 直接分割
    if "\n" in text:
        lines = text.split("\n")
    else:
        # 无换行的连续文本: 在中文编号 (1、2、3… 等) 前插入换行
        # 匹配: 非开头位置的 "数字+、" 或 "数字+."
        split_text = re.sub(r'(?<=\S)(\d+)[、.](?=\S)', r'\n\1、', text)
        lines = split_text.split("\n")

    # 过滤空行并格式化
    result = []
    for line in lines:
        formatted = _fix_list_format(line)
        if formatted:
            result.append(formatted)
    return result


def build_markdown(query, city, jobs, details=None, status="采集中"):
    """生成 Obsidian markdown (汇总表格 + 职位详情)

    jobs: [{rank, title, salary, company, location, experience, education, tags, url}, ...]
    details: {job_id: detail_dict, ...} 或 None
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_title = re.sub(r"[\r\n]+", " ", query)[:50]
    details = details or {}

    lines = [
        "---",
        "tags: [智联招聘, 职位搜索]",
        f'title: "智联招聘搜索 - {safe_title}"',
        f'query: {json.dumps(query, ensure_ascii=False)}',
        f'city: "{city}"',
        'source: "智联招聘"',
        f"count: {len(jobs)}",
        f"createTime: {datetime.now().isoformat(timespec='seconds')}",
        f"status: {status}",
        "---",
        "",
        f"# 智联招聘搜索 - {query}",
        "",
        f"> **关键词**: {query} | **城市**: {city} | **数量**: {len(jobs)} | **时间**: {now}",
        "",
        "## 职位列表",
        "",
        "| # | 职位 | 薪资 | 公司 | 地区 | 经验 | 学历 | 职位描述 |",
        "|---|------|------|------|------|------|------|------|",
    ]

    for j in jobs:
        rank = j.get("rank", "")
        title = _clean_cell(j.get("title", "无标题"))
        salary = _clean_cell(j.get("salary", ""))
        company = _clean_cell(j.get("company", ""))
        location = _clean_cell(j.get("location", ""))
        experience = _clean_cell(j.get("experience", ""))
        education = _clean_cell(j.get("education", ""))
        url = j.get("url", "")

        # 职位名做成链接
        if url:
            title_cell = f"[{title}]({url})"
        else:
            title_cell = title

        # 职位描述列: Obsidian wikilink 跳转到详情区段
        job_id = _extract_job_id(url)
        has_detail = bool(details and details.get(job_id))
        if has_detail:
            safe_name = j.get("title", "").replace("|", "-")
            heading = f"{rank}. {safe_name}"
            desc_cell = f"[[#{heading}\\|查看描述]]"
        else:
            desc_cell = ""

        # job_id 作为注释保存在表格中, 续传时使用
        id_comment = f"<!-- id:{job_id} -->" if job_id else ""
        lines.append(f"| {rank} | {title_cell} | {salary} | {company} | {location} | {experience} | {education} | {desc_cell} {id_comment}")

    lines.append("")

    # 职位详情区段
    if details:
        lines.append("## 职位详情")
        lines.append("")
        for j in jobs:
            url = j.get("url", "")
            job_id = _extract_job_id(url)
            detail = details.get(job_id)
            if not detail:
                continue

            lines.extend(_build_detail_section(j, detail))
            lines.append("")

    return "\n".join(lines)


def _build_detail_section(job, detail):
    """生成单个职位详情的 markdown 行列表 (公司信息 + 职位描述, 放入 Callout)"""
    rank = job.get("rank", "")
    name = job.get("title", "无标题")
    safe_name = name.replace("|", "-")
    lines = [f"### {rank}. {safe_name}", ""]

    # Callout 内容行
    callout_lines = []

    # 公司信息 (含行业/规模/融资阶段)
    company = detail.get("company", "") or job.get("company", "")
    company_desc = detail.get("company_desc", "")
    company_parts = []
    if company:
        company_parts.append(company)
    if company_desc:
        company_parts.append(company_desc)
    if company_parts:
        callout_lines.append(f"- **公司**: {' · '.join(company_parts)}")

    # 薪资 + 福利
    salary = detail.get("salary", "")
    welfare = detail.get("welfare", "")
    if salary:
        callout_lines.append(f"- **薪资**: {salary}")
    if welfare:
        callout_lines.append(f"- **福利**: {welfare}")

    # 工作地址
    address = detail.get("address", "")
    if address:
        callout_lines.append(f"- **地址**: {address}")

    # 技能要求
    skills = detail.get("skills", "")
    if skills:
        callout_lines.append(f"- **技能**: {skills}")

    # 职位描述
    description = detail.get("description", "")
    if description:
        callout_lines.append("")
        callout_lines.append("- **职位描述**:")
        callout_lines.append("")
        callout_lines.extend(_split_description(description))

    # 公司介绍
    company_intro = detail.get("company_intro", "")
    if company_intro:
        callout_lines.append("")
        callout_lines.append("- **公司介绍**:")
        callout_lines.append("")
        callout_lines.extend(_split_description(company_intro))

    # 用 Callout 包裹
    lines.append("> [!info]- 职位详情")
    for cl in callout_lines:
        lines.append(f"> {cl}" if cl else ">")

    return lines


def get_md_path(query, city):
    """确定 markdown 文件路径 (文件名含来源前缀, 冲突时加时间戳)"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    safe_source = sanitize_filename(SOURCE)[:20]
    safe_name = sanitize_filename(query)[:60] or "untitled"
    safe_city = sanitize_filename(city)[:20]
    md_path = OUTPUT_ROOT / f"{safe_source}_{safe_name}_{safe_city}.md"
    if md_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        md_path = OUTPUT_ROOT / f"{safe_source}_{safe_name}_{safe_city}_{ts}.md"
    return md_path


def write_markdown(md_path, md_content):
    """写入 markdown 到指定路径 (覆盖)"""
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def main():
    log("=" * 60)
    log("智联招聘职位搜索采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取搜索参数 (命令行参数优先, 无参数时弹窗)
    query = None
    city = "宁波"
    limit = 20
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
        # 第 5 个参数: --start-index=N 或直接数字
        if len(sys.argv) >= 5:
            arg5 = sys.argv[4].strip()
            if arg5.startswith("--start-index="):
                try:
                    start_index = max(1, int(arg5.split("=")[1]))
                except (ValueError, IndexError):
                    pass
            else:
                try:
                    start_index = max(1, int(arg5))
                except ValueError:
                    pass
    else:
        query, city, limit = show_search_dialog()

    if not query:
        log("未输入关键词, 退出")
        return 1

    log(f"关键词: {query}")
    log(f"城市: {city}")
    log(f"数量: {limit}")

    # 2. 调用 opencli zhaopin search
    log("搜索中, 请稍候 (约 15-30 秒)...")
    jobs = search_jobs(query, city, limit)

    if not jobs:
        log("未获取到职位, 退出")
        return 2

    log(f"获取到 {len(jobs)} 个职位")

    # 3. 断点续传: 读取已有详情
    details = {}
    md_path = get_md_path(query, city)

    if start_index > 1 and md_path.exists():
        log(f"断点续传: 从第 {start_index} 个开始, 尝试读取已有详情...")
        try:
            existing_content = md_path.read_text(encoding="utf-8")
            detail_pattern = re.compile(r'^### (\d+)\. (.+)$', re.MULTILINE)
            existing_details = detail_pattern.findall(existing_content)
            if existing_details:
                log(f"已有 {len(existing_details)} 个详情, 将跳过这些职位")
        except Exception as e:
            log(f"读取已有文件失败: {e}, 将从头开始")

    # 写入初始文件 (如果不存在), 状态为"采集中"
    if not md_path.exists() or start_index == 1:
        md_content = build_markdown(query, city, jobs, details=details, status="采集中")
        write_markdown(md_path, md_content)
        log(f"已创建 (采集中): {md_path}")
    else:
        existing_content = md_path.read_text(encoding="utf-8")
        md_content = update_frontmatter_status(existing_content, "采集中")
        write_markdown(md_path, md_content)
        log(f"继续写入 (采集中): {md_path}")

    # 4. 逐个调用 zhaopin detail, 每获取一个就更新文件
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

        url = job.get("url", "")
        job_id = _extract_job_id(url)
        if not url and not job_id:
            log(f"  [{i}/{len(jobs)}] {job.get('title', '?')[:30]} - 无 URL, 跳过")
            continue

        log(f"  [{i}/{len(jobs)}] {job.get('title', '?')[:30]} - 获取详情...")

        # 防风控: 第 2 条起随机等待
        if i > 1:
            wait = random.uniform(DETAIL_INTERVAL_MIN, DETAIL_INTERVAL_MAX)
            time.sleep(wait)

        # 批次暂停: 每 N 个职位暂停一次
        if i > 1 and (i - 1) % BATCH_SIZE == 0:
            wait = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
            log(f"  已完成 {i-1} 个, 批次暂停 {wait:.0f}秒...")
            _sleep_with_heartbeat(wait, "批次暂停")

        # 连续失败冷却
        if consecutive_fails >= DETAIL_COOLDOWN_FAILS:
            wait = random.uniform(DETAIL_COOLDOWN_WAIT_MIN, DETAIL_COOLDOWN_WAIT_MAX)
            log(f"  连续失败 {consecutive_fails} 次, 冷却 {wait:.0f}秒...")
            _sleep_with_heartbeat(wait, "冷却")
            consecutive_fails = 0

        # 重试逻辑
        got_detail = None
        for attempt in range(1, DETAIL_RETRY_MAX + 2):  # 1次初试 + N次重试
            try:
                got_detail = get_job_detail(url)
                if got_detail:
                    break
            except Exception as e:
                log(f"  [{i}/{len(jobs)}] 第{attempt}次异常: {e}")
                got_detail = None

            if attempt <= DETAIL_RETRY_MAX:
                wait = random.uniform(DETAIL_RETRY_WAIT_MIN, DETAIL_RETRY_WAIT_MAX)
                log(f"  [{i}/{len(jobs)}] 第{attempt}次失败, {wait:.0f}秒后重试...")
                _sleep_with_heartbeat(wait, "重试等待")

        if got_detail:
            details[job_id] = got_detail
            log(f"  [{i}/{len(jobs)}] OK")
            consecutive_fails = 0
        else:
            fail_count += 1
            consecutive_fails += 1
            log(f"  [{i}/{len(jobs)}] 失败 (重试{DETAIL_RETRY_MAX}次仍失败)")

        # 每次获取后立即更新文件
        md_content = build_markdown(query, city, jobs, details=details)
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
