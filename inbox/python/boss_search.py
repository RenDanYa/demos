# -*- coding: utf-8 -*-
"""BOSS直聘职位搜索采集

调用 opencli boss search 命令, 把搜索结果(职位/薪资/公司/地区/技能等)保存为 Obsidian Markdown。

用法:
    python boss_search.py                          # 弹窗输入关键词 + 城市 + 数量
    python boss_search.py "外贸"                    # 默认北京, 采集 15 个
    python boss_search.py "外贸" 上海               # 指定城市
    python boss_search.py "外贸" 上海 30            # 指定城市 + 数量
    python boss_search.py "外贸" 上海 30 1-3年 本科  # 指定经验 + 学历
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
DETAIL_INTERVAL_MIN = 3
DETAIL_INTERVAL_MAX = 5

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
        f"城市名 (如 北京/上海/杭州, 留空=北京):",
        initialvalue="北京",
        parent=root,
    )
    city = (city or "北京").strip() or "北京"

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
        f"经验: {'/'.join(EXPERIENCE_OPTIONS)}\n(留空=不限)",
        initialvalue="",
        parent=root,
    )
    exp = (exp or "").strip()

    # 5. 学历 (可选)
    degree = simpledialog.askstring(
        "学历要求 (可选)",
        f"学历: {'/'.join(DEGREE_OPTIONS)}\n(留空=不限)",
        initialvalue="",
        parent=root,
    )
    degree = (degree or "").strip()

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


def build_markdown(query, city, jobs, details=None, experience="", degree=""):
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
        "status: 已采集",
        "---",
        "",
        f"# BOSS直聘搜索 - {query}",
        "",
        f"> **关键词**: {query} | **城市**: {city} | **数量**: {len(jobs)} | **时间**: {now}{filter_desc}",
        "",
        "## 职位列表",
        "",
        "| # | 职位 | 薪资 | 公司 | 地区 | 经验 | 学历 | 职位描述 |",
        "|---|------|------|------|------|------|------|------|",
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

        # 职位描述列: 锚点跳转到详情区段
        sid = j.get("security_id", "")
        has_detail = bool(details and details.get(sid))
        if has_detail:
            anchor = _make_anchor(f"{i}. {j.get('name', '')}")
            desc_cell = f"[查看描述](#{anchor})"
        else:
            desc_cell = ""

        lines.append(f"| {i} | {name_cell} | {salary} | {company} | {area} | {exp} | {deg} | {desc_cell} |")

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


def _make_anchor(text):
    """将标题文本转为 markdown 锚点 (小写, 去特殊字符, 空格转连字符)"""
    anchor = text.lower()
    anchor = re.sub(r"[^\w\s\u4e00-\u9fff]", "", anchor)  # 保留字母数字下划线中文空格
    anchor = re.sub(r"\s+", "-", anchor.strip())
    return anchor


def _build_detail_section(index, job, detail):
    """生成单个职位详情的 markdown 行列表 (仅公司信息 + 职位描述)"""
    name = job.get("name", "无标题")
    lines = [f"### {index}. {name}"]

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
        lines.append(f"**公司**: {' · '.join(company_parts)}")

    # 职位描述
    description = detail.get("description", "")
    if description:
        lines.append("")
        lines.append("**职位描述**:")
        lines.append("")
        lines.append(description)

    return lines


def _clean_cell(val):
    """清洗表格单元格内容: 转义管道符, 替换换行"""
    if not val:
        return ""
    return str(val).replace("|", "\\|").replace("\n", " ").replace("\r", "")


def write_markdown(query, city, md_content):
    """保存 markdown 文件, 返回路径"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(query)[:60] or "untitled"
    # 文件名含城市, 便于区分不同城市的搜索
    safe_city = sanitize_filename(city)[:20]
    md_path = OUTPUT_ROOT / f"{safe_name}_{safe_city}.md"

    # 同名文件已存在时, 加时间戳后缀避免覆盖
    if md_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        md_path = OUTPUT_ROOT / f"{safe_name}_{safe_city}_{ts}.md"

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
    city = "北京"
    limit = 15
    experience = ""
    degree = ""
    if len(sys.argv) >= 2:
        query = sys.argv[1].strip()
        if len(sys.argv) >= 3:
            city = sys.argv[2].strip() or "北京"
        if len(sys.argv) >= 4:
            try:
                limit = max(1, min(100, int(sys.argv[3])))
            except ValueError:
                pass
        if len(sys.argv) >= 5:
            experience = sys.argv[4].strip()
        if len(sys.argv) >= 6:
            degree = sys.argv[5].strip()
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

    # 3. 逐个调用 boss detail 获取职位详情
    log(f"开始获取职位详情 ({len(jobs)} 个, 间隔 {DETAIL_INTERVAL_MIN}-{DETAIL_INTERVAL_MAX}秒)...")
    details = {}
    fail_count = 0
    for i, job in enumerate(jobs, 1):
        sid = job.get("security_id", "")
        if not sid:
            log(f"  [{i}/{len(jobs)}] {job.get('name', '?')[:30]} - 无 security_id, 跳过")
            continue

        log(f"  [{i}/{len(jobs)}] {job.get('name', '?')[:30]} - 获取详情...")

        # 防风控: 第 2 条起随机等待
        if i > 1:
            wait = random.uniform(DETAIL_INTERVAL_MIN, DETAIL_INTERVAL_MAX)
            time.sleep(wait)

        detail = get_job_detail(sid)
        if detail:
            details[sid] = detail
            log(f"  [{i}/{len(jobs)}] OK")
        else:
            fail_count += 1
            log(f"  [{i}/{len(jobs)}] 失败")

    log(f"详情获取完成: 成功 {len(details)}/{len(jobs)}, 失败 {fail_count}")

    # 4. 生成 markdown
    md_content = build_markdown(query, city, jobs, details=details, experience=experience, degree=degree)
    md_path = write_markdown(query, city, md_content)
    log(f"已保存: {md_path}")
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
