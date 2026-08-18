# -*- coding: utf-8 -*-
"""鱼泡网批量发送简历

从 Markdown 笔记中提取职位 URL, 调用 opencli yupao apply 一键发送简历。
直接在原 Markdown 表格中添加"投递状态"列实时更新。

鱼泡网是蓝领招聘平台, 投递按钮文字为"发送简历" (不同于智联的"立即投递")。
鱼泡网受阿里云 WAF 保护, 首次访问需通过 JS 验证, 投递超时给足时间。
鱼泡网无 check 命令 (不像智联有 check), 只做投递 + 简单复核 (重跑 apply 检测 already_applied)。

用法:
    python yupao_apply.py <md_file>
    python yupao_apply.py "d:/obsidian/demo/05_long_project/招聘/鱼泡网_焊工_宁波.md"
    python yupao_apply.py <md_file> --start 5      # 从第 5 个开始投递 (断点续传)
    python yupao_apply.py <md_file> --delay 3       # 每次投递间隔 3 秒 (默认 5 秒)
    python yupao_apply.py <md_file> --dry-run       # 只打印不投递
    python yupao_apply.py <md_file> --no-recheck    # 跳过投递后复核
    python yupao_apply.py <md_file> --recheck-only # 只复核 (跳过投递, 直接重跑 apply 检测已发送状态)

输出:
    - 终端实时日志
    - 投递记录: d:/obsidian/demo/05_long_project/招聘/投递记录_鱼泡.md
    - 断点续传: 同目录 yupao_apply_processed.txt
    - 直接修改原 md 文件 (添加"投递状态"列)
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import log, run_opencli  # noqa: E402

# ============ 配置 ============
OUTPUT_DIR = Path("d:/obsidian/demo/05_long_project/招聘")
LOG_DIR = OUTPUT_DIR / "程序运行日志"
PROCESSED_LOG = OUTPUT_DIR / "yupao_apply_processed.txt"
RECORD_FILE = OUTPUT_DIR / "投递记录_鱼泡.md"
RECHECK_FILE = OUTPUT_DIR / "投递复核记录_鱼泡.md"
TIMEOUT_APPLY = 180   # 鱼泡 WAF 验证 + 滚动加载, 给足时间
DEFAULT_DELAY = 5
RECHECK_DELAY = 3

# 鱼泡网 URL 正则
# URL 模式: https://www.yupao.com/zhaogong/442258949/AcvuvyCtBSFsJ2SY1uTxK1FX5b.html
# jobId=数字, token=字母数字混合
URL_PATTERN = re.compile(r'https?://www\.yupao\.com/zhaogong/(\d+)/([A-Za-z0-9]+)\.htm[^\s)]*')

# CLI 内部浏览器命令超时 (鱼泡 WAF 验证可能耗时较长)
os.environ.setdefault("OPENCLI_BROWSER_COMMAND_TIMEOUT", "180")


def extract_urls(md_path):
    """从 Markdown 文件提取职位 URL, 保持出现顺序

    返回: [(url, job_id, token), ...]
    """
    content = md_path.read_text(encoding="utf-8")
    urls = []
    seen = set()
    for m in URL_PATTERN.finditer(content):
        url = m.group(0)
        # 去除 URL 后的查询参数和锚点
        url_clean = re.sub(r'\?.*$', '', url)
        url_clean = re.sub(r'#.*$', '', url_clean)
        job_id = m.group(1)
        token = m.group(2)
        if job_id not in seen:
            seen.add(job_id)
            urls.append((url_clean, job_id, token))
    return urls


def apply_job(url):
    """调用 opencli yupao apply 发送简历

    返回: (status, message, title) 或 (None, error, "")
    status 取值: success / failed / already_applied / need_login / no_apply_button / unknown
    """
    args = ["yupao", "apply", url, "-f", "json"]
    ok, stdout, err = run_opencli(args, TIMEOUT_APPLY)
    if not ok:
        return None, err or "opencli call failed", ""

    try:
        data = json.loads(stdout)
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            return item.get("status", "unknown"), item.get("message", ""), item.get("title", "")
        return None, "no data in json output", ""
    except json.JSONDecodeError as e:
        return None, f"json parse error: {e}", ""


def append_record(md_path, job_id, title, status, message):
    """追加投递记录到 投递记录_鱼泡.md"""
    RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not RECORD_FILE.exists():
        header = f"""---
title: 鱼泡网投递记录
created: {time.strftime('%Y-%m-%d %H:%M:%S')}
---

# 鱼泡网投递记录

| 时间 | 来源文件 | 职位ID | 职位标题 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
"""
        RECORD_FILE.write_text(header, encoding="utf-8")

    now = time.strftime('%Y-%m-%d %H:%M:%S')
    source = md_path.stem
    # 鱼泡详情页 URL 需 token, 这里只用 job_id 构造简化链接 (浏览路径)
    row = f"| {now} | {source} | [{job_id}](https://www.yupao.com/zhaogong/{job_id}/) | {title} | {status} | {message} |\n"
    with open(RECORD_FILE, "a", encoding="utf-8") as f:
        f.write(row)


def append_recheck_record(job_id, title, status, message):
    """追加复核记录到 投递复核记录_鱼泡.md"""
    RECHECK_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not RECHECK_FILE.exists():
        header = f"""---
title: 鱼泡网投递复核记录
created: {time.strftime('%Y-%m-%d %H:%M:%S')}
---

# 鱼泡网投递复核记录

> 投递完成后逐个重跑 apply 检测状态, 未投递的会补投。

| 时间 | 职位ID | 职位标题 | 复核状态 | 备注 |
| --- | --- | --- | --- | --- |
"""
        RECHECK_FILE.write_text(header, encoding="utf-8")

    now = time.strftime('%Y-%m-%d %H:%M:%S')
    row = f"| {now} | [{job_id}](https://www.yupao.com/zhaogong/{job_id}/) | {title} | {status} | {message} |\n"
    with open(RECHECK_FILE, "a", encoding="utf-8") as f:
        f.write(row)


def update_md_row_status(md_path, job_id, status_text):
    """直接更新原 Markdown 文件中 job_id 对应行的"投递状态"列

    - 表头如无"投递状态"列, 自动添加, 并给所有数据行追加空状态列
    - 数据行: 替换最后一列(状态列)为 status_text
    """
    if not md_path.exists():
        return False

    content = md_path.read_text(encoding="utf-8")
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = content.split('\n')

    # 1. 定位表头行 (含"职位", 后跟分隔行)
    header_idx = None
    for i, line in enumerate(lines):
        if '| 职位' in line and 'http' not in line:
            if i + 1 < len(lines) and re.match(r'^\|\s*-+\s*\|\s*-+\s*\|', lines[i + 1]):
                header_idx = i
                break

    if header_idx is None:
        return False

    # 2. 定位分隔行
    separator_idx = None
    for i in range(header_idx + 1, min(header_idx + 3, len(lines))):
        if re.match(r'^\|\s*-+\s*\|\s*-+\s*\|', lines[i]):
            separator_idx = i
            break

    if separator_idx is None:
        return False

    # 3. 表头如无"投递状态"列, 添加列
    has_status_col = '投递状态' in lines[header_idx]
    if not has_status_col:
        lines[header_idx] = lines[header_idx].rstrip() + ' 投递状态 |'
        lines[separator_idx] = lines[separator_idx].rstrip() + ' --- |'

        for i in range(separator_idx + 1, len(lines)):
            line = lines[i]
            if not line.startswith('|'):
                break
            if 'yupao.com' not in line:
                continue
            lines[i] = line.rstrip() + '  |'

    # 4. 更新指定 job_id 数据行的状态列
    updated = False
    for i in range(separator_idx + 1, len(lines)):
        line = lines[i]
        if not line.startswith('|'):
            break
        if job_id not in line or 'yupao.com' not in line:
            continue

        stripped = line.rstrip()
        if not stripped.endswith('|'):
            stripped = stripped + ' |'

        parts = stripped.split('|')
        if len(parts) >= 2:
            parts[-2] = ' ' + status_text + ' '
            lines[i] = '|'.join(parts)
            updated = True
        break

    if updated:
        md_path.write_text('\n'.join(lines), encoding="utf-8")

    return updated


def main():
    parser = argparse.ArgumentParser(
        description="鱼泡网批量发送简历",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python yupao_apply.py "d:/obsidian/demo/05_long_project/招聘/鱼泡网_焊工_宁波.md"
    python yupao_apply.py <md_file> --start 5
    python yupao_apply.py <md_file> --delay 3
    python yupao_apply.py <md_file> --dry-run
    python yupao_apply.py <md_file> --recheck-only
""",
    )
    parser.add_argument("md_file", help="Markdown 文件路径 (含职位 URL)")
    parser.add_argument("--start", type=int, default=1, help="从第 N 个开始投递 (断点续传, 默认 1)")
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY, help=f"投递间隔秒数 (默认 {DEFAULT_DELAY})")
    parser.add_argument("--dry-run", action="store_true", help="只打印不投递")
    parser.add_argument("--no-recheck", action="store_true", help="跳过投递后复核")
    parser.add_argument("--recheck-only", action="store_true", help="只复核 (跳过投递阶段, 重跑 apply 检测状态)")
    args = parser.parse_args()

    md_path = Path(args.md_file)
    if not md_path.exists():
        print(f"错误: 文件不存在 {md_path}")
        sys.exit(1)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log("=" * 60)
    log("鱼泡网批量发送简历 启动")
    log(f"OPENCLI_CMD: {('node', 'd:/voice/opencli-main/dist/main.js')}")
    log(f"来源文件: {md_path}")
    log(f"投递间隔: {args.delay} 秒")
    log(f"起始序号: {args.start}")
    log(f"测试模式: {'是' if args.dry_run else '否'}")
    log(f"投递后复核: {'否' if args.no_recheck else '是'}")
    log(f"只复核模式: {'是' if args.recheck_only else '否'}")
    log("=" * 60)

    # 提取 URL
    url_items = extract_urls(md_path)
    log(f"提取到 {len(url_items)} 个职位 URL")

    if not url_items:
        log("未提取到 URL, 退出")
        return

    # ============ 只复核模式 ============
    if args.recheck_only:
        if args.start > 1:
            url_items = url_items[args.start - 1:]
            log(f"跳过前 {args.start - 1} 个, 剩余 {len(url_items)} 个待复核")

        log("=" * 60)
        log("只复核模式 启动 (跳过投递阶段)")
        log(f"待复核职位: {len(url_items)} 个")
        log(f"复核间隔: {RECHECK_DELAY} 秒")
        log("=" * 60)

        recheck_applied = 0
        recheck_not_applied = 0
        recheck_fail = 0
        reapply_success = 0
        reapply_fail = 0

        for i, (url, job_id, token) in enumerate(url_items, 1):
            log(f"[{i}/{len(url_items)}] 复核 {job_id} ...")

            # 鱼泡无 check 命令, 用 apply 检测 (already_applied = 已发送, success/need_login = 未发送)
            status = None
            message = ""
            title = ""
            for attempt in range(2):
                status, message, title = apply_job(url)
                if status is not None:
                    break
                log(f"  尝试 {attempt + 1}/2 失败: {str(message)[:80]}")
                if attempt == 0:
                    time.sleep(3)

            if status is None:
                log(f"  复核失败: {message}")
                recheck_fail += 1
                append_recheck_record(job_id, "", "error", message[:100])
                update_md_row_status(md_path, job_id, "⚠ 复核失败")
            elif status == "already_applied":
                log(f"  ✓ 已发送: {message}")
                recheck_applied += 1
                append_recheck_record(job_id, title, status, message)
                update_md_row_status(md_path, job_id, "✓ 已发送")
            elif status == "success":
                # 复核时返回 success 说明之前未发送, 这次发送成功了
                log(f"  ✓ 复核时发送成功 (之前未发送): {message}")
                recheck_not_applied += 1
                reapply_success += 1
                append_recheck_record(job_id, title, "reapplied", message)
                update_md_row_status(md_path, job_id, "✓ 补发送成功")
            elif status == "need_login":
                log(f"  ⚠ 需要登录: {message}")
                recheck_fail += 1
                append_recheck_record(job_id, title, status, message)
                update_md_row_status(md_path, job_id, "⚠ 需登录")
                log("  请在 Chrome 中登录鱼泡网后重试")
                break
            elif status == "no_apply_button":
                log(f"  ⚠ 未找到发送按钮: {message}")
                recheck_fail += 1
                append_recheck_record(job_id, title, status, message[:100])
                update_md_row_status(md_path, job_id, "⚠ 无发送按钮")
            elif status == "failed":
                log(f"  ✗ 发送失败: {message}")
                recheck_fail += 1
                append_recheck_record(job_id, title, status, message[:100])
                update_md_row_status(md_path, job_id, "✗ 发送失败")
            else:
                log(f"  复核状态: {status} - {message}")
                recheck_fail += 1
                append_recheck_record(job_id, title, status, message[:100])
                update_md_row_status(md_path, job_id, f"⚠ {status}")

            if i < len(url_items):
                time.sleep(RECHECK_DELAY)

        log("")
        log("========== 复核完成 ==========")
        log(f"已发送 (符合预期): {recheck_applied}")
        log(f"未发送 → 补发送成功: {reapply_success}")
        log(f"未发送 → 补发送失败: {reapply_fail}")
        log(f"复核失败/异常: {recheck_fail}")
        log(f"复核记录: {RECHECK_FILE}")
        return

    # ============ 投递阶段 ============
    # 断点续传: 读取已处理
    processed = set()
    if PROCESSED_LOG.exists():
        processed = set(
            line.strip()
            for line in PROCESSED_LOG.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    log(f"已处理 (将跳过): {len(processed)}")

    if args.start > 1:
        url_items = url_items[args.start - 1:]
        log(f"跳过前 {args.start - 1} 个, 剩余 {len(url_items)} 个")

    success = 0
    fail = 0
    skip = 0
    already = 0
    applied_urls = []  # [(job_id, url, title), ...]

    for i, (url, job_id, token) in enumerate(url_items, 1):
        # 断点续传
        if job_id in processed:
            skip += 1
            continue

        log(f"[{i}/{len(url_items)}] 发送简历 {job_id} ...")

        if args.dry_run:
            log(f"  (测试模式) 跳过实际发送")
            continue

        # 重试 2 次
        status = None
        message = ""
        title = ""
        for attempt in range(2):
            status, message, title = apply_job(url)
            if status is not None:
                break
            log(f"  尝试 {attempt + 1}/2 失败: {str(message)[:80]}")
            if attempt == 0:
                time.sleep(3)

        if status is None:
            log(f"  失败: {message}")
            fail += 1
            append_record(md_path, job_id, "", "error", message[:100])
            update_md_row_status(md_path, job_id, "✗ 失败")
        elif status == "success":
            log(f"  成功: {message}")
            success += 1
            append_record(md_path, job_id, title, status, message)
            applied_urls.append((job_id, url, title))
            update_md_row_status(md_path, job_id, "✓ 已发送")
        elif status == "already_applied":
            log(f"  已发送过: {message}")
            already += 1
            append_record(md_path, job_id, title, status, message)
            applied_urls.append((job_id, url, title))
            update_md_row_status(md_path, job_id, "✓ 已发送")
        elif status == "need_login":
            log(f"  需要登录: {message}")
            log("  请在 Chrome 中登录鱼泡网后重试")
            append_record(md_path, job_id, title, status, message)
            update_md_row_status(md_path, job_id, "⚠ 需登录")
            break
        elif status == "no_apply_button":
            log(f"  未找到发送按钮: {message}")
            fail += 1
            append_record(md_path, job_id, title, status, message[:100])
            update_md_row_status(md_path, job_id, "✗ 无发送按钮")
        elif status == "failed":
            log(f"  发送失败: {message}")
            fail += 1
            append_record(md_path, job_id, title, status, message[:100])
            update_md_row_status(md_path, job_id, "✗ 发送失败")
        else:
            log(f"  状态: {status} - {message}")
            fail += 1
            append_record(md_path, job_id, title, status, message[:100])
            update_md_row_status(md_path, job_id, f"✗ {status}")

        # 记录已处理
        try:
            with open(PROCESSED_LOG, "a", encoding="utf-8") as pf:
                pf.write(job_id + "\n")
        except Exception:
            pass

        # 间隔
        if i < len(url_items):
            time.sleep(args.delay)

    log("")
    log("========== 发送阶段完成 ==========")
    log(f"成功: {success}")
    log(f"已发送过: {already}")
    log(f"失败: {fail}")
    log(f"跳过(已处理): {skip}")
    log(f"投递记录: {RECORD_FILE}")

    # ============ 投递后复核 ============
    if args.dry_run:
        log("测试模式, 跳过复核")
        return

    if args.no_recheck:
        log("已通过 --no-recheck 跳过复核")
        return

    if not applied_urls:
        log("无发送成功的记录, 跳过复核")
        return

    log("")
    log("=" * 60)
    log("投递复核 启动")
    log(f"待复核职位: {len(applied_urls)} 个")
    log(f"复核间隔: {RECHECK_DELAY} 秒")
    log("=" * 60)

    recheck_applied = 0
    recheck_not_applied = 0
    recheck_fail = 0
    reapply_success = 0
    reapply_fail = 0

    for i, (job_id, url, title) in enumerate(applied_urls, 1):
        log(f"[{i}/{len(applied_urls)}] 复核 {job_id} ...")

        # 鱼泡无 check 命令, 用 apply 检测
        status = None
        message = ""
        for attempt in range(2):
            status, message, _ = apply_job(url)
            if status is not None:
                break
            log(f"  尝试 {attempt + 1}/2 失败: {str(message)[:80]}")
            if attempt == 0:
                time.sleep(3)

        if status is None:
            log(f"  复核失败: {message}")
            recheck_fail += 1
            append_recheck_record(job_id, title, "error", message[:100])
            update_md_row_status(md_path, job_id, "⚠ 复核失败")
        elif status == "already_applied":
            log(f"  ✓ 已发送: {message}")
            recheck_applied += 1
            append_recheck_record(job_id, title, status, message)
            update_md_row_status(md_path, job_id, "✓ 已发送")
        elif status == "success":
            # 复核时返回 success 说明之前未发送, 这次发送成功了
            log(f"  ✗ 未发送! 补发送成功: {message}")
            recheck_not_applied += 1
            reapply_success += 1
            append_recheck_record(job_id, title, "reapplied", message)
            update_md_row_status(md_path, job_id, "✓ 补发送成功")
        elif status == "need_login":
            log(f"  ⚠ 需要登录: {message}")
            recheck_fail += 1
            append_recheck_record(job_id, title, status, message)
            update_md_row_status(md_path, job_id, "⚠ 需登录")
            log("  请在 Chrome 中登录鱼泡网后重试")
            break
        elif status == "no_apply_button":
            log(f"  ⚠ 未找到发送按钮: {message}")
            recheck_fail += 1
            append_recheck_record(job_id, title, status, message[:100])
            update_md_row_status(md_path, job_id, "⚠ 无发送按钮")
        elif status == "failed":
            log(f"  ✗ 发送失败: {message}")
            recheck_fail += 1
            append_recheck_record(job_id, title, status, message[:100])
            update_md_row_status(md_path, job_id, "✗ 发送失败")
        else:
            log(f"  复核状态: {status} - {message}")
            recheck_fail += 1
            append_recheck_record(job_id, title, status, message[:100])
            update_md_row_status(md_path, job_id, f"⚠ {status}")

        if i < len(applied_urls):
            time.sleep(RECHECK_DELAY)

    log("")
    log("========== 复核完成 ==========")
    log(f"已发送 (符合预期): {recheck_applied}")
    log(f"未发送 → 补发送成功: {reapply_success}")
    log(f"未发送 → 补发送失败: {reapply_fail}")
    log(f"复核失败/异常: {recheck_fail}")
    log(f"复核记录: {RECHECK_FILE}")


if __name__ == "__main__":
    main()
