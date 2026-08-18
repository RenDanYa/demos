# -*- coding: utf-8 -*-
"""前程无忧批量投递职位

从 Markdown 笔记中提取职位 URL, 调用 opencli job51 apply 一键投递。
投递完成后自动复核 (访问 URL 检测按钮状态), 未投递的补投。

用法:
    python job51_apply.py <md_file>
    python job51_apply.py "d:/obsidian/demo/05_long_project/招聘/前程无忧_录入_宁波多区.md"
    python job51_apply.py <md_file> --start 5      # 从第 5 个开始投递 (断点续传)
    python job51_apply.py <md_file> --delay 3       # 每次投递间隔 3 秒 (默认 5 秒)
    python job51_apply.py <md_file> --dry-run       # 只打印不投递
    python job51_apply.py <md_file> --no-recheck    # 跳过投递后复核
    python job51_apply.py <md_file> --recheck-only # 只复核 (跳过投递, 直接访问 URL 校验并更新状态列)

输出:
    - 终端实时日志
    - 投递记录: d:/obsidian/demo/05_long_project/招聘/投递记录.md
    - 断点续传: 同目录 _apply_processed.txt
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import log, run_opencli  # noqa: E402

# ============ 配置 ============
OUTPUT_DIR = Path("d:/obsidian/demo/05_long_project/招聘")
LOG_DIR = OUTPUT_DIR / "程序运行日志"
PROCESSED_LOG = OUTPUT_DIR / "job51_apply_processed.txt"
RECORD_FILE = OUTPUT_DIR / "投递记录.md"
RECHECK_FILE = OUTPUT_DIR / "投递复核记录.md"
TIMEOUT_APPLY = 90
TIMEOUT_CHECK = 60
DEFAULT_DELAY = 5
RECHECK_DELAY = 3

# 职位 URL 正则 (支持 https://jobs.51job.com/ningbo/123456.html 或 ningbo-jbq 带区后缀)
URL_PATTERN = re.compile(r'https://jobs\.51job\.com/[\w-]+/(\d+)\.html')


def extract_urls(md_path):
    """从 Markdown 文件提取职位 URL, 保持出现顺序"""
    content = md_path.read_text(encoding="utf-8")
    urls = []
    seen = set()
    for m in URL_PATTERN.finditer(content):
        url = m.group(0)
        job_id = m.group(1)
        if job_id not in seen:
            seen.add(job_id)
            urls.append(url)
    return urls


def apply_job(url):
    """调用 opencli job51 apply 投递单个职位

    返回: (status, message) 或 (None, error)
    """
    args = ["job51", "apply", url, "-f", "json"]
    ok, stdout, err = run_opencli(args, TIMEOUT_APPLY)
    if not ok:
        return None, err or "opencli call failed"

    try:
        data = json.loads(stdout)
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            return item.get("status", "unknown"), item.get("message", "")
        return None, "no data in json output"
    except json.JSONDecodeError as e:
        return None, f"json parse error: {e}"


def check_job(url):
    """调用 opencli job51 check 校验职位是否已投递 (不执行投递)

    返回: (status, message) 或 (None, error)
        status: applied / not_applied / need_login / verify / offline
    """
    args = ["job51", "check", url, "-f", "json"]
    ok, stdout, err = run_opencli(args, TIMEOUT_CHECK)
    if not ok:
        return None, err or "opencli call failed"

    try:
        data = json.loads(stdout)
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            return item.get("status", "unknown"), item.get("message", "")
        return None, "no data in json output"
    except json.JSONDecodeError as e:
        return None, f"json parse error: {e}"


def append_record(md_path, job_id, title, status, message):
    """追加投递记录到 投递记录.md"""
    RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 初始化文件 (带 frontmatter 和表头)
    if not RECORD_FILE.exists():
        header = f"""---
title: 前程无忧投递记录
created: {time.strftime('%Y-%m-%d %H:%M:%S')}
---

# 前程无忧投递记录

| 时间 | 来源文件 | 职位ID | 职位标题 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
"""
        RECORD_FILE.write_text(header, encoding="utf-8")

    now = time.strftime('%Y-%m-%d %H:%M:%S')
    source = md_path.stem
    row = f"| {now} | {source} | [{job_id}](https://jobs.51job.com/ningbo/{job_id}.html) | {title} | {status} | {message} |\n"
    with open(RECORD_FILE, "a", encoding="utf-8") as f:
        f.write(row)


def append_recheck_record(job_id, title, status, message):
    """追加复核记录到 投递复核记录.md (独立文件, 不污染投递记录)"""
    RECHECK_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not RECHECK_FILE.exists():
        header = f"""---
title: 前程无忧投递复核记录
created: {time.strftime('%Y-%m-%d %H:%M:%S')}
---

# 前程无忧投递复核记录

> 投递完成后逐个访问 URL 校验是否真的已投递, 未投递的会补投。

| 时间 | 职位ID | 职位标题 | 复核状态 | 备注 |
| --- | --- | --- | --- | --- |
"""
        RECHECK_FILE.write_text(header, encoding="utf-8")

    now = time.strftime('%Y-%m-%d %H:%M:%S')
    row = f"| {now} | [{job_id}](https://jobs.51job.com/ningbo/{job_id}.html) | {title} | {status} | {message} |\n"
    with open(RECHECK_FILE, "a", encoding="utf-8") as f:
        f.write(row)


def update_md_row_status(md_path, job_id, status_text):
    """直接更新原 Markdown 文件中 job_id 对应行的"投递状态"列。

    - 表头如无"投递状态"列, 自动添加, 并给所有数据行追加空状态列
    - 数据行: 替换最后一列(状态列)为 status_text
    """
    if not md_path.exists():
        return False

    content = md_path.read_text(encoding="utf-8")
    # 统一行尾, 兼容 \r\n 和 \n
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = content.split('\n')

    # 1. 定位表头行 (含"职位", 不含 URL; 后跟分隔行)
    header_idx = None
    for i, line in enumerate(lines):
        if '| 职位' in line and 'http' not in line:
            # 验证下一行是分隔行
            if i + 1 < len(lines) and re.match(r'^\|\s*-+\s*\|\s*-+\s*\|', lines[i + 1]):
                header_idx = i
                break

    if header_idx is None:
        return False

    # 2. 定位分隔行 (紧跟表头, 至少 2 列短横线即可)
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

        # 给所有数据行追加空状态列
        for i in range(separator_idx + 1, len(lines)):
            line = lines[i]
            if not line.startswith('|'):
                break  # 表格结束
            if 'jobs.51job.com' not in line:
                continue  # 非数据行
            lines[i] = line.rstrip() + '  |'  # 追加空状态列

    # 4. 更新指定 job_id 数据行的状态列
    updated = False
    for i in range(separator_idx + 1, len(lines)):
        line = lines[i]
        if not line.startswith('|'):
            break  # 表格结束
        if job_id not in line or 'jobs.51job.com' not in line:
            continue

        stripped = line.rstrip()
        # 确保以 | 结尾
        if not stripped.endswith('|'):
            stripped = stripped + ' |'

        # split('|') => ['', col1, col2, ..., colN, '']
        # 状态列在 parts[-2]
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
        description="前程无忧批量投递职位",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python job51_apply.py "d:/obsidian/demo/05_long_project/招聘/前程无忧_录入_宁波多区.md"
    python job51_apply.py <md_file> --start 5
    python job51_apply.py <md_file> --delay 3
    python job51_apply.py <md_file> --dry-run
""",
    )
    parser.add_argument("md_file", help="Markdown 文件路径 (含职位 URL)")
    parser.add_argument("--start", type=int, default=1, help="从第 N 个开始投递 (断点续传, 默认 1)")
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY, help=f"投递间隔秒数 (默认 {DEFAULT_DELAY})")
    parser.add_argument("--dry-run", action="store_true", help="只打印不投递")
    parser.add_argument("--no-recheck", action="store_true", help="跳过投递后复核")
    parser.add_argument("--recheck-only", action="store_true", help="只复核 (跳过投递阶段, 直接访问所有 URL 校验并更新状态列)")
    args = parser.parse_args()

    md_path = Path(args.md_file)
    if not md_path.exists():
        print(f"错误: 文件不存在 {md_path}")
        sys.exit(1)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log("=" * 60)
    log("前程无忧批量投递 启动")
    log(f"OPENCLI_CMD: {('node', 'd:/voice/opencli-main/dist/main.js')}")
    log(f"来源文件: {md_path}")
    log(f"投递间隔: {args.delay} 秒")
    log(f"起始序号: {args.start}")
    log(f"测试模式: {'是' if args.dry_run else '否'}")
    log(f"投递后复核: {'否' if args.no_recheck else '是'}")
    log(f"只复核模式: {'是' if args.recheck_only else '否'}")
    log("=" * 60)

    # 提取 URL
    urls = extract_urls(md_path)
    log(f"提取到 {len(urls)} 个职位 URL")

    if not urls:
        log("未提取到 URL, 退出")
        return

    # ============ 只复核模式 ============
    # 跳过投递阶段, 直接对全部 URL 逐个 check 并更新状态列
    if args.recheck_only:
        # 支持 --start 续复核
        if args.start > 1:
            urls = urls[args.start - 1:]
            log(f"跳过前 {args.start - 1} 个, 剩余 {len(urls)} 个待复核")

        log("=" * 60)
        log("只复核模式 启动 (跳过投递阶段)")
        log(f"待复核职位: {len(urls)} 个")
        log(f"复核间隔: {RECHECK_DELAY} 秒")
        log("=" * 60)

        recheck_applied = 0
        recheck_not_applied = 0
        recheck_fail = 0
        reapply_success = 0
        reapply_fail = 0

        for i, url in enumerate(urls, 1):
            job_id = URL_PATTERN.search(url).group(1)
            log(f"[{i}/{len(urls)}] 复核 {job_id} ...")

            status = None
            message = ""
            for attempt in range(2):
                status, message = check_job(url)
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
            elif status == "applied":
                log(f"  ✓ 已投递: {message}")
                recheck_applied += 1
                append_recheck_record(job_id, "", status, message)
                update_md_row_status(md_path, job_id, "✓ 已投递")
            elif status == "not_applied":
                log(f"  ✗ 未投递! 开始补投: {message}")
                recheck_not_applied += 1
                append_recheck_record(job_id, "", status, message)
                update_md_row_status(md_path, job_id, "✗ 未投递")

                rstatus, rmsg = apply_job(url)
                if rstatus == "success":
                    log(f"  ✓ 补投成功: {rmsg}")
                    reapply_success += 1
                    append_recheck_record(job_id, "", "reapplied", rmsg)
                    update_md_row_status(md_path, job_id, "✓ 补投成功")
                elif rstatus == "already_applied":
                    log(f"  ✓ 补投时发现已投递: {rmsg}")
                    reapply_success += 1
                    append_recheck_record(job_id, "", "applied", rmsg)
                    update_md_row_status(md_path, job_id, "✓ 已投递")
                else:
                    log(f"  ✗ 补投失败: {rstatus} - {rmsg}")
                    reapply_fail += 1
                    append_recheck_record(job_id, "", f"reapply_{rstatus}", rmsg)
                    update_md_row_status(md_path, job_id, "✗ 补投失败")
            elif status == "verify":
                log(f"  ⚠ 触发风控: {message}")
                recheck_fail += 1
                append_recheck_record(job_id, "", status, message)
                update_md_row_status(md_path, job_id, "⚠ 风控")
                log("  ⚠ 复核触发滑动验证, 立即停止复核 (避免账号风控)")
                log(f"  续复核命令: python job51_apply.py \"{md_path}\" --recheck-only --start {i + 1}")
                break
            elif status == "need_login":
                log(f"  ⚠ 需要登录: {message}")
                recheck_fail += 1
                append_recheck_record(job_id, "", status, message)
                update_md_row_status(md_path, job_id, "⚠ 需登录")
                log("  请在 Chrome 中登录 51job 后重试")
                break
            else:
                log(f"  复核状态: {status} - {message}")
                recheck_fail += 1
                append_recheck_record(job_id, "", status, message)
                update_md_row_status(md_path, job_id, f"⚠ {status}")

            if i < len(urls):
                time.sleep(RECHECK_DELAY)

        log("")
        log("========== 复核完成 ==========")
        log(f"已投递: {recheck_applied}")
        log(f"未投递 → 补投成功: {reapply_success}")
        log(f"未投递 → 补投失败: {reapply_fail}")
        log(f"复核失败/异常: {recheck_fail}")
        log(f"复核记录: {RECHECK_FILE}")
        return

    # 断点续传: 读取已处理
    processed = set()
    if PROCESSED_LOG.exists():
        processed = set(
            line.strip()
            for line in PROCESSED_LOG.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    log(f"已处理 (将跳过): {len(processed)}")

    # 跳过到 start
    if args.start > 1:
        urls = urls[args.start - 1:]
        log(f"跳过前 {args.start - 1} 个, 剩余 {len(urls)} 个")

    success = 0
    fail = 0
    skip = 0
    already = 0
    # 记录所有投递成功 (含已投递过) 的 (job_id, url), 用于投递后复核
    applied_urls = []

    for i, url in enumerate(urls, 1):
        job_id = URL_PATTERN.search(url).group(1)

        # 断点续传
        if job_id in processed:
            skip += 1
            continue

        log(f"[{i}/{len(urls)}] 投递 {job_id} ...")

        if args.dry_run:
            log(f"  (测试模式) 跳过实际投递")
            continue

        # 重试 2 次
        status = None
        message = ""
        for attempt in range(2):
            status, message = apply_job(url)
            if status is not None:
                break
            log(f"  尝试 {attempt + 1}/2 失败: {str(message)[:80]}")
            if attempt == 0:
                time.sleep(3)

        if status is None:
            log(f"  失败: {message}")
            fail += 1
            append_record(md_path, job_id, "", "error", message[:100])
            update_md_row_status(md_path, job_id, f"✗ 失败")
        elif status == "success":
            log(f"  成功: {message}")
            success += 1
            append_record(md_path, job_id, "", status, message)
            applied_urls.append((job_id, url))
            update_md_row_status(md_path, job_id, "✓ 已投递")
        elif status == "already_applied":
            log(f"  已投递过: {message}")
            already += 1
            append_record(md_path, job_id, "", status, message)
            # 已投递过的不加入复核列表 (无需复核)
            update_md_row_status(md_path, job_id, "✓ 已投递")
        elif status == "need_login":
            log(f"  需要登录: {message}")
            log("  请在 Chrome 中登录 51job 后重试")
            append_record(md_path, job_id, "", status, message)
            update_md_row_status(md_path, job_id, "⚠ 需登录")
            break  # 需要登录, 中止
        elif status == "verify":
            log(f"  触发风控: {message}")
            append_record(md_path, job_id, "", status, message)
            update_md_row_status(md_path, job_id, "⚠ 风控")
            log("  ⚠ 检测到滑动验证, 立即停止批量投递 (避免账号被风控封禁)")
            log("  请手动访问 51job 搜索页解除风控后, 使用 --start 参数续投")
            log(f"  续投命令: python job51_apply.py \"{md_path}\" --start {i + 1}")
            break  # 触发风控, 立即停止
        else:
            log(f"  状态: {status} - {message}")
            fail += 1
            append_record(md_path, job_id, "", status, message)
            update_md_row_status(md_path, job_id, f"✗ {status}")

        # 记录已处理
        try:
            with open(PROCESSED_LOG, "a", encoding="utf-8") as pf:
                pf.write(job_id + "\n")
        except Exception:
            pass

        # 间隔
        if i < len(urls):
            time.sleep(args.delay)

    log("")
    log("========== 投递阶段完成 ==========")
    log(f"成功: {success}")
    log(f"已投递过: {already}")
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
        log("无投递成功的记录, 跳过复核")
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

    for i, (job_id, url) in enumerate(applied_urls, 1):
        log(f"[{i}/{len(applied_urls)}] 复核 {job_id} ...")

        # 重试 2 次
        status = None
        message = ""
        for attempt in range(2):
            status, message = check_job(url)
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
        elif status == "applied":
            log(f"  ✓ 已投递: {message}")
            recheck_applied += 1
            append_recheck_record(job_id, "", status, message)
            update_md_row_status(md_path, job_id, "✓ 已投递")
        elif status == "not_applied":
            # 复核发现未投递, 立即补投
            log(f"  ✗ 未投递! 开始补投: {message}")
            recheck_not_applied += 1
            append_recheck_record(job_id, "", status, message)
            update_md_row_status(md_path, job_id, "✗ 未投递")

            # 补投
            rstatus, rmsg = apply_job(url)
            if rstatus == "success":
                log(f"  ✓ 补投成功: {rmsg}")
                reapply_success += 1
                append_recheck_record(job_id, "", "reapplied", rmsg)
                update_md_row_status(md_path, job_id, "✓ 补投成功")
            elif rstatus == "already_applied":
                log(f"  ✓ 补投时发现已投递: {rmsg}")
                reapply_success += 1
                append_recheck_record(job_id, "", "applied", rmsg)
                update_md_row_status(md_path, job_id, "✓ 已投递")
            else:
                log(f"  ✗ 补投失败: {rstatus} - {rmsg}")
                reapply_fail += 1
                append_recheck_record(job_id, "", f"reapply_{rstatus}", rmsg)
                update_md_row_status(md_path, job_id, f"✗ 补投失败")
        elif status == "verify":
            log(f"  ⚠ 触发风控: {message}")
            recheck_fail += 1
            append_recheck_record(job_id, "", status, message)
            update_md_row_status(md_path, job_id, "⚠ 风控")
            log("  ⚠ 复核触发滑动验证, 立即停止复核 (避免账号风控)")
            log(f"  续复核命令: 重新运行 (脚本未支持 --recheck-start, 请手动重跑)")
            break
        elif status == "need_login":
            log(f"  ⚠ 需要登录: {message}")
            recheck_fail += 1
            append_recheck_record(job_id, "", status, message)
            update_md_row_status(md_path, job_id, "⚠ 需登录")
            log("  请在 Chrome 中登录 51job 后重试")
            break
        else:
            log(f"  复核状态: {status} - {message}")
            recheck_fail += 1
            append_recheck_record(job_id, "", status, message)
            update_md_row_status(md_path, job_id, f"⚠ {status}")

        if i < len(applied_urls):
            time.sleep(RECHECK_DELAY)

    log("")
    log("========== 复核完成 ==========")
    log(f"已投递 (符合预期): {recheck_applied}")
    log(f"未投递 → 补投成功: {reapply_success}")
    log(f"未投递 → 补投失败: {reapply_fail}")
    log(f"复核失败/异常: {recheck_fail}")
    log(f"复核记录: {RECHECK_FILE}")


if __name__ == "__main__":
    main()
