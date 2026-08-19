# -*- coding: utf-8 -*-
"""鱼泡网职位搜索采集

调用 opencli yupao search 命令, 把搜索结果(职位/薪资/公司/地区/标签等)保存为 Obsidian Markdown。

鱼泡网是蓝领招聘平台(建筑/工厂/物流/司机等), 覆盖浙江主要城市。

实现说明:
    鱼泡网 search 命令通过 --city 参数传城市代码(如 a388=宁波), 不支持区级代码,
    所以多区域搜索时改为调用全市搜索一次, 然后在 Python 端按 location 字段过滤。
    鱼泡网 CLI 内部通过滚动虚拟列表加载, --limit 控制返回数量上限, 无需分页参数。
    鱼泡网受阿里云 WAF 保护, 首次访问需通过 JS 验证, 搜索超时给足时间。
    鱼泡网无 detail 命令, 本脚本只采集列表(表格), 不获取详情。

用法:
    python yupao_search.py                          # 弹窗: 关键词 + 城市 + 宁波区域多选 + 数量
    python yupao_search.py "焊工"                    # 宁波全市, 20 个
    python yupao_search.py "焊工" 宁波               # 指定城市
    python yupao_search.py "焊工" 宁波 30            # 指定城市 + 数量 (简写, 纯数字视为 limit)
    python yupao_search.py "焊工" 宁波 鄞州区,海曙区 # 指定城市 + 多区域 (仅宁波支持区级过滤)
    python yupao_search.py "焊工" 宁波 鄞州区,海曙区 30  # 多区域 + 数量 (每区最多 N 个)

城市名称见 CITY_CODES 常量 (浙江主要城市 + 全国)。
宁波区域名称见 NINGBO_DISTRICTS 常量 (海曙区/江北区/北仑区/镇海区/鄞州区/奉化区/余姚市/慈溪市/象山县/宁海县)。
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
SOURCE = "鱼泡网"
OUTPUT_ROOT = OBSIDIAN_ROOT / "05_long_project" / "招聘"
# 搜索超时基线 (WAF 验证最多 80s + 首屏渲染), 每个职位约需 2.5s 滚动加载
# limit=20 → 150s, limit=50 → 215s, limit=100 → 340s
TIMEOUT_SEARCH_BASE = 90
TIMEOUT_SEARCH_PER_ITEM = 2.5
TIMEOUT_SEARCH_MIN = 150  # 即使 limit 很小也至少给 150s (WAF 冷启动)


def _compute_search_timeout(limit):
    """根据 limit 动态计算搜索超时 (秒)

    鱼泡网搜索耗时组成:
      - WAF 验证 + 首屏渲染: 最多 80s (冷启动重试另加 30s)
      - 虚拟列表滚动: 每屏 3s wait + 0-10s waitLoading, 每屏加载 ~7 个职位
      - 每个 limit 大约需要 2.5s 滚动时间
    """
    return max(TIMEOUT_SEARCH_MIN, int(TIMEOUT_SEARCH_BASE + limit * TIMEOUT_SEARCH_PER_ITEM))

# 鱼泡网城市代码映射 (cityCode 用于构建搜索/浏览 URL)
# 数据来源: yupao/search.ts 中 CITY_CODES 常量
CITY_CODES = {
    "全国": "a0",
    # 浙江
    "宁波": "a388",
    "杭州": "a383",
    "湖州": "a384",
    "嘉兴": "a385",
    "金华": "a386",
    "丽水": "a387",
    "绍兴": "a389",
    "台州": "a390",
    "温州": "a391",
    "舟山": "a392",
    "衢州": "a393",
}

# 城市选项 (用于弹窗提示)
CITY_OPTIONS = list(CITY_CODES.keys())

# 宁波固定城市, 区级名称列表 (用于多区域搜索)
# 鱼泡网 search 不支持区级代码, 只能全市搜索后 Python 端按 location 过滤
NINGBO_DISTRICTS = [
    "海曙区", "江北区", "北仑区", "镇海区", "鄞州区",
    "奉化区", "余姚市", "慈溪市", "象山县", "宁海县",
]

# CLI 内部浏览器命令超时 (鱼泡 WAF 验证可能耗时较长)
# 留空在此处设置默认值, search_jobs() 会按 limit 动态覆盖
os.environ.setdefault("OPENCLI_BROWSER_COMMAND_TIMEOUT", "240")


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


def resolve_city_code(city_name):
    """将城市名解析为鱼泡城市代码

    支持:
        - 城市名 (如 "宁波" → "a388")
        - 直接代码 (如 "a388" → "a388")
        - 模糊匹配 (如 "波" → "宁波" 的代码)
    未匹配则返回 "a0" (全国)
    """
    if not city_name:
        return "a0"
    # 直接传入代码 (如 a388)
    if re.match(r'^a\d+$', city_name, re.IGNORECASE):
        return city_name
    # 精确匹配
    if city_name in CITY_CODES:
        return CITY_CODES[city_name]
    # 模糊匹配
    for name, code in CITY_CODES.items():
        if name in city_name or city_name in name:
            return code
    return "a0"


def show_search_dialog():
    """tkinter 弹窗: 关键词 + 城市 + 宁波区域多选 + 数量

    返回: (kw, city, districts, limit)
        - city: 城市名 (如 "宁波")
        - districts: list[str] 选中的区域名 (空列表表示全市; 仅宁波支持区级过滤)
    """
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
        "鱼泡网搜索",
        "请输入搜索关键词 (如 焊工、电工、司机):",
        initialvalue="焊工",
        parent=root,
    )
    if not kw or not kw.strip():
        root.destroy()
        return None, "宁波", [], 0
    kw = kw.strip()

    # 2. 城市
    city = _show_city_select(root, kw)

    # 3. 宁波区域多选 (仅当城市为宁波时)
    districts = []
    if city == "宁波":
        districts = _show_district_multiselect(root, kw)

    # 4. 数量
    limit_str = simpledialog.askstring(
        "采集数量",
        f"搜索「{kw}」前几个职位? (1-100)\n(多区域时, 每个区域各取 N 个)",
        initialvalue="20",
        parent=root,
    )
    try:
        limit = max(1, min(100, int(limit_str)))
    except (TypeError, ValueError):
        limit = 20

    root.destroy()
    return kw, city, districts, limit


def _show_city_select(parent, kw):
    """tkinter 单选城市

    返回: 城市名 (如 "宁波")
    """
    import tkinter as tk

    win = tk.Toplevel(parent)
    win.title(f"选择城市 - 搜索「{kw}」")
    win.attributes("-topmost", True)
    win.geometry("280x380")

    tk.Label(win, text="选择城市 (仅宁波支持区级过滤):").pack(pady=8, padx=10, anchor="w")

    listbox = tk.Listbox(win, selectmode=tk.SINGLE, height=12, exportselection=False)
    listbox.pack(fill="both", expand=True, padx=10, pady=5)

    for c in CITY_OPTIONS:
        listbox.insert(tk.END, c)
    # 默认选中宁波
    listbox.selection_set(CITY_OPTIONS.index("宁波"))
    listbox.see(CITY_OPTIONS.index("宁波"))

    result = {"selected": "宁波"}

    def on_ok():
        sel_idx = listbox.curselection()
        if sel_idx:
            result["selected"] = CITY_OPTIONS[sel_idx[0]]
        win.destroy()

    btn_frame = tk.Frame(win)
    btn_frame.pack(fill="x", padx=10, pady=8)
    tk.Button(btn_frame, text="确定", command=on_ok).pack(side="right", padx=5)

    win.wait_window()
    return result["selected"]


def _show_district_multiselect(parent, kw):
    """tkinter Listbox 多选宁波区域

    返回: list[str] 选中的区域名 (空列表 = 全市)
    """
    import tkinter as tk

    win = tk.Toplevel(parent)
    win.title(f"宁波区域多选 - 搜索「{kw}」")
    win.attributes("-topmost", True)
    win.geometry("320x420")

    tk.Label(win, text="选择宁波区域 (按住 Ctrl/Shift 多选, 留空=全市):").pack(pady=8, padx=10, anchor="w")

    listbox = tk.Listbox(win, selectmode=tk.MULTIPLE, height=12, exportselection=False)
    listbox.pack(fill="both", expand=True, padx=10, pady=5)

    for d in NINGBO_DISTRICTS:
        listbox.insert(tk.END, d)

    result = {"selected": []}

    def on_ok():
        sel_idx = listbox.curselection()
        result["selected"] = [NINGBO_DISTRICTS[i] for i in sel_idx]
        win.destroy()

    def on_clear():
        listbox.selection_clear(0, tk.END)

    btn_frame = tk.Frame(win)
    btn_frame.pack(fill="x", padx=10, pady=8)
    tk.Button(btn_frame, text="清空 (全市)", command=on_clear).pack(side="left", padx=5)
    tk.Button(btn_frame, text="确定", command=on_ok).pack(side="right", padx=5)

    win.wait_window()
    return result["selected"]


def _parse_cli_args():
    """无 tkinter 时从命令行参数解析

    用法:
        python yupao_search.py <关键词> [城市] [区域1,区域2,...] [数量]
        城市默认宁波, 区域用逗号分隔 (仅宁波支持), 留空 = 全市
        例: python yupao_search.py 焊工 宁波 鄞州区,海曙区 20
    """
    if len(sys.argv) < 2:
        return None, "宁波", [], 0
    kw = sys.argv[1].strip()
    city = "宁波"
    districts = []
    limit = 20

    if len(sys.argv) >= 3:
        city = sys.argv[2].strip() or "宁波"
    if len(sys.argv) >= 4:
        arg3 = sys.argv[3].strip()
        if arg3:
            if arg3.isdigit():
                # 纯数字当作 limit (允许 `python yupao_search.py 焊工 宁波 30` 简写)
                try:
                    limit = max(1, min(100, int(arg3)))
                except ValueError:
                    pass
            else:
                districts = [d.strip() for d in arg3.split(",") if d.strip()]
    if len(sys.argv) >= 5:
        try:
            limit = max(1, min(100, int(sys.argv[4])))
        except ValueError:
            pass
    return kw, city, districts, limit


def _extract_job_id(url):
    """从鱼泡 URL 中提取职位 ID

    如 https://www.yupao.com/zhaogong/443690098/token.html → 443690098
    """
    if not url:
        return ""
    m = re.search(r'/zhaogong/(\d+)/', url)
    if m:
        return m.group(1)
    # 兜底: 直接取 URL 中的数字串
    m = re.search(r'/zhaogong/(\d+)', url)
    if m:
        return m.group(1)
    return url


def search_jobs(query, city, limit):
    """调用 opencli yupao search

    query: 搜索关键词 (空字符串则浏览默认职位列表)
    city: 城市名 (如 "宁波") 或城市代码 (如 "a388")
    limit: 返回职位数量上限
    返回: [{rank, title, salary, company, location, tags, url}, ...] 或 None
    """
    city_code = resolve_city_code(city)
    args = [
        "yupao", "search",
    ]
    # query 作为位置参数 (留空则浏览默认列表)
    if query:
        args.append(query)
    args.extend([
        "--city", city_code,
        "--limit", str(limit),
        "-f", "json",
    ])

    # 按 limit 动态计算超时: CLI 内部浏览器命令超时 + Python 端子进程超时
    # Python 超时 > CLI 超时 (多 30s), 确保 CLI 先自己结束并返回错误信息,
    # Python 端能拿到完整的 timeout 原因, 而不是粗暴地 kill 掉子进程
    browser_timeout = _compute_search_timeout(limit)
    python_timeout = browser_timeout + 30
    os.environ["OPENCLI_BROWSER_COMMAND_TIMEOUT"] = str(browser_timeout)

    log(f"调用 opencli yupao search (city={city}[{city_code}], limit={limit}, 超时 浏览器={browser_timeout}s/Python={python_timeout}s)")
    ok, stdout, err = run_opencli(args, python_timeout)
    if not ok:
        log(f"yupao search 调用失败: {err}")
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


def search_jobs_multi_district(query, city, districts, limit):
    """对选中的多个宁波区域进行搜索并过滤

    实现方式: 鱼泡网 search 不支持区级代码, 只能全市搜索一次,
    然后在 Python 端按 location 字段过滤选中区域。
    鱼泡网 CLI 内部通过 --limit 控制返回数量(含滚动加载), 无分页参数,
    所以多区域时直接用较大的 limit 取回样本再过滤。

    query: 搜索关键词
    city: 城市名 (应为 "宁波")
    districts: list[str] 区域名 (如 ["鄞州区", "海曙区"])
    limit: 每个区域最多保留多少个职位
    返回: list[dict] 过滤后的职位列表
    """
    # 选了多个区且每区要 limit 个时, 需要更大的样本量
    target_total = limit * len(districts) * 2
    # 鱼泡网 --limit 上限 100 (CLI 内部限制), 取 min
    fetch_limit = min(100, max(target_total, limit * 2))

    log(f"--- 全市搜索 (city={city}, 目标 {target_total} 个, 取回 {fetch_limit} 个) ---")
    all_jobs = search_jobs(query, city, fetch_limit)

    if not all_jobs:
        log("全市搜索未获取到职位")
        return []

    log(f"全市共获取 {len(all_jobs)} 个职位, 开始按区域过滤...")

    # 按 location 字段过滤
    # 鱼泡 location 格式可能多样: "宁波·鄞州" / "宁波 鄞州区" / "鄞州区" / "宁波"
    def extract_district(loc):
        """从 location 提取区简称 (去掉 '宁波' 前缀 + 分隔符 + '区/市/县' 后缀)

        返回: 区简称 (如 "鄞州" / "海曙" / "余姚"), 便于和 NINGBO_DISTRICTS 匹配
        """
        if not loc:
            return ""
        # 去 "宁波" 前缀 + 任意分隔符 (空格/中点/连字符)
        s = re.sub(r'^宁波[\s·\-]*', '', loc.strip())
        # 取第一个分隔符前的部分 (区名), 再去掉 "区/市/县" 后缀
        s = re.split(r'[\s·\-]', s, maxsplit=1)[0]
        s = re.sub(r'[市区县]$', '', s)
        return s.strip()

    # 构造 "区简称 → 原区域名" 映射 (如 "鄞州" → "鄞州区")
    short_to_name = {re.sub(r'[市区县]$', '', d): d for d in districts}

    # 按区域分组
    by_district = {d: [] for d in districts}
    seen_ids = set()
    other_count = 0

    for j in all_jobs:
        url = j.get("url", "")
        job_id = _extract_job_id(url)
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        loc = j.get("location", "")
        district_short = extract_district(loc)

        if district_short in short_to_name:
            original_name = short_to_name[district_short]
            if len(by_district[original_name]) < limit:
                by_district[original_name].append(j)
        else:
            other_count += 1

    # 合并结果, 重排 rank
    merged = []
    new_rank = 0
    for district_name in districts:
        jobs_in_d = by_district.get(district_name, [])
        log(f"  {district_name}: {len(jobs_in_d)} 个")
        for j in jobs_in_d:
            new_rank += 1
            j["rank"] = new_rank
            merged.append(j)

    log(f"过滤后总计: {len(merged)} 个 (全市共 {len(all_jobs)}, 其他区域 {other_count})")
    return merged


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


def _clean_cell(val):
    """清洗表格单元格内容: 转义管道符, 替换换行"""
    if not val:
        return ""
    return str(val).replace("|", "\\|").replace("\n", " ").replace("\r", "")


def build_markdown(query, city, jobs, status="已采集", districts=None):
    """生成 Obsidian markdown (汇总表格)

    鱼泡网无 detail 命令, 仅生成职位列表表格。

    jobs: [{rank, title, salary, company, location, tags, url}, ...]
    districts: list[str] 宁波区域列表 (用于 frontmatter 显示, 仅宁波有效)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_title = re.sub(r"[\r\n]+", " ", query)[:50] if query else "默认列表"

    # 区域信息字符串
    if districts:
        districts_str = ", ".join(districts)
        districts_yaml = json.dumps(districts, ensure_ascii=False)
    else:
        districts_str = "全市"
        districts_yaml = "[]"

    lines = [
        "---",
        "tags: [鱼泡网, 职位搜索, 蓝领]",
        f'title: "鱼泡网搜索 - {safe_title} ({city} {districts_str})"',
        f'query: {json.dumps(query or "", ensure_ascii=False)}',
        f'city: "{city}"',
        f'districts: {districts_yaml}',
        'source: "鱼泡网"',
        f"count: {len(jobs)}",
        f"createTime: {datetime.now().isoformat(timespec='seconds')}",
        f"status: {status}",
        "---",
        "",
        f"# 鱼泡网搜索 - {query or '默认列表'} ({city} {districts_str})",
        "",
        f"> **关键词**: {query or '(默认)'} | **城市**: {city} | **区域**: {districts_str} | **数量**: {len(jobs)} | **时间**: {now}",
        "",
        "## 职位列表",
        "",
        "| # | 职位 | 薪资 | 公司 | 地区 | 标签 |",
        "|---|------|------|------|------|------|",
    ]

    for j in jobs:
        rank = j.get("rank", "")
        title = _clean_cell(j.get("title", "无标题"))
        salary = _clean_cell(j.get("salary", ""))
        company = _clean_cell(j.get("company", ""))
        location = _clean_cell(j.get("location", ""))
        tags = _clean_cell(j.get("tags", ""))
        url = j.get("url", "")

        # 职位名做成链接
        if url:
            title_cell = f"[{title}]({url})"
        else:
            title_cell = title

        # job_id 作为注释保存在表格中, 便于后续投递脚本提取
        job_id = _extract_job_id(url)
        id_comment = f"<!-- id:{job_id} -->" if job_id else ""
        lines.append(f"| {rank} | {title_cell} | {salary} | {company} | {location} | {tags} {id_comment}")

    lines.append("")

    return "\n".join(lines)


def get_md_path(query, city, districts=None):
    """确定 markdown 文件路径 (文件名含来源前缀, 冲突时加时间戳)

    districts: list[str] 宁波区域列表
        - 空或 None → city 作为后缀
        - 有值 → 用 "鄞州海曙" 这样的区简称拼接 (超过 3 个区用 "宁波多区")
    """
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    safe_source = sanitize_filename(SOURCE)[:20]
    safe_name = sanitize_filename(query or "default")[:60] or "untitled"

    if districts:
        if len(districts) <= 3:
            # 拼接区简称 (去掉"区"/"市"/"县"后缀)
            short_names = []
            for d in districts:
                short = re.sub(r'[市区县]$', '', d)
                short_names.append(short)
            city_suffix = "".join(short_names)
        else:
            city_suffix = "宁波多区"
    else:
        city_suffix = sanitize_filename(city)[:20]

    md_path = OUTPUT_ROOT / f"{safe_source}_{safe_name}_{city_suffix}.md"
    if md_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        md_path = OUTPUT_ROOT / f"{safe_source}_{safe_name}_{city_suffix}_{ts}.md"
    return md_path


def write_markdown(md_path, md_content):
    """写入 markdown 到指定路径 (覆盖)"""
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def main():
    log("=" * 60)
    log("鱼泡网职位搜索采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取搜索参数 (命令行参数优先, 无参数时弹窗)
    query = None
    city = "宁波"
    districts = []  # 多选区域 (空 = 全市; 仅宁波支持)
    limit = 20

    if len(sys.argv) >= 2:
        query = sys.argv[1].strip()
        if len(sys.argv) >= 3:
            city = sys.argv[2].strip() or "宁波"
        if len(sys.argv) >= 4:
            arg3 = sys.argv[3].strip()
            if arg3:
                if arg3.isdigit():
                    # 纯数字当作 limit (允许 `python yupao_search.py 焊工 宁波 30` 简写)
                    try:
                        limit = max(1, min(100, int(arg3)))
                    except ValueError:
                        pass
                else:
                    districts = [d.strip() for d in arg3.split(",") if d.strip()]
        if len(sys.argv) >= 5:
            try:
                limit = max(1, min(100, int(sys.argv[4])))
            except ValueError:
                pass
    else:
        query, city, districts, limit = show_search_dialog()

    if not query:
        log("未输入关键词, 退出")
        return 1

    # 校验: 仅宁波支持区级过滤
    if districts and city != "宁波":
        log(f"城市 {city} 不支持区级过滤, 忽略区域选择")
        districts = []

    log(f"关键词: {query}")
    log(f"城市: {city} (代码: {resolve_city_code(city)})")
    if districts:
        log(f"区域(多选): {', '.join(districts)}")
    else:
        log(f"区域: 全市")
    log(f"数量: {limit}")

    # 2. 调用 opencli yupao search
    expected_timeout = _compute_search_timeout(limit)
    log(f"搜索中, 请稍候 (鱼泡 WAF 验证 + 滚动加载, limit={limit}, 最长 {expected_timeout}s)...")
    if districts:
        jobs = search_jobs_multi_district(query, city, districts, limit)
    else:
        jobs = search_jobs(query, city, limit)

    if not jobs:
        log("未获取到职位, 退出 (可能原因: WAF 验证未通过/关键词无结果/网络超时)")
        return 2

    log(f"获取到 {len(jobs)} 个职位 (去重后)")

    # 3. 生成并写入 markdown (鱼泡网无 detail 命令, 直接标记已采集)
    md_path = get_md_path(query, city, districts)
    md_content = build_markdown(query, city, jobs, status="已采集", districts=districts)
    write_markdown(md_path, md_content)
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
