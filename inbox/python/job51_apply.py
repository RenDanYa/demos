# -*- coding: utf-8 -*-
"""前程无忧批量投递职位

从 Markdown 笔记中提取职位 URL, 调用 opencli job51 apply 一键投递。

用法:
    python job51_apply.py <md_file>
    python job51_apply.py "d:/obsidian/demo/05_long_project/招聘/前程无忧_录入_宁波多区.md"
    python job51_apply.py <md_file> --start 5      # 从第 5 个开始投递 (断点续传)
    python job51_apply.py <md_file> --delay 3       # 每次投递间隔 3 秒 (默认 5 秒)
    python job51_apply.py <md_file> --dry-run       # 只打印不投递

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
TIMEOUT_APPLY = 90
DEFAULT_DELAY = 5

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
    log("=" * 60)

    # 提取 URL
    urls = extract_urls(md_path)
    log(f"提取到 {len(urls)} 个职位 URL")

    if not urls:
        log("未提取到 URL, 退出")
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
        elif status == "success":
            log(f"  成功: {message}")
            success += 1
            append_record(md_path, job_id, "", status, message)
        elif status == "already_applied":
            log(f"  已投递过: {message}")
            already += 1
            append_record(md_path, job_id, "", status, message)
        elif status == "need_login":
            log(f"  需要登录: {message}")
            log("  请在 Chrome 中登录 51job 后重试")
            append_record(md_path, job_id, "", status, message)
            break  # 需要登录, 中止
        else:
            log(f"  状态: {status} - {message}")
            fail += 1
            append_record(md_path, job_id, "", status, message)

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
    log("========== 完成 ==========")
    log(f"成功: {success}")
    log(f"已投递过: {already}")
    log(f"失败: {fail}")
    log(f"跳过(已处理): {skip}")
    log(f"投递记录: {RECORD_FILE}")


if __name__ == "__main__":
    main()
