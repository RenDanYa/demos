#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zread_read.py — 读取 GitHub 仓库在 zread.ai 的 AI 解读 wiki。

底层调用 opencli-upstream 的 zread read 适配器（纯 HTTP 公开接口，
无需浏览器、无需登录、不弹任何窗口）。

与全局 opencli 命令完全隔离：
  - 全程用绝对路径 node d:\\voice\\opencli-upstream\\dist\\src\\main.js 调用，
    不经过全局 `opencli`（它指向 opencli-main，那里没有 zread 站点）
  - read.js 是 CLI 适配器（注册进运行时），不能单独 node 执行，必须走 main.js
  - subprocess 的 cwd 固定为 opencli-upstream，保证 manifest 解析不受当前目录影响

用法：
  python zread_read.py --repo pymupdf/PyMuPDF --list
  python zread_read.py --repo pymupdf/PyMuPDF --page 1
  python zread_read.py --repo pymupdf/PyMuPDF --slug 2-quick-start --lang zh
  python zread_read.py --repo pymupdf/PyMuPDF --all --save d:\\obsidian\\demo\\inbox
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

# ---- 常量：绝对路径，与全局 opencli 完全隔离 ----
NODE_CANDIDATES = ["node", r"D:\软件安装\nodejs\node.exe"]
CLI_ENTRY = r"d:\voice\opencli-upstream\dist\src\main.js"
CLI_CWD = r"d:\voice\opencli-upstream"
REQUEST_TIMEOUT = 120   # 单次请求超时（秒）
RETRY_ATTEMPTS = 2      # zread 偶发瞬时 504，自动重试一次
RETRY_WAIT = 3


def find_node() -> str:
    for cand in NODE_CANDIDATES:
        if shutil.which(cand) or Path(cand).is_file():
            return cand
    sys.exit("[错误] 找不到 node，请确认 nodejs 在 PATH 中或安装于 D:\\软件安装\\nodejs")


def run_cli(cli_args: list) -> list:
    """调用 opencli-upstream 的 zread 命令，返回 JSON 行列表。"""
    cmd = [find_node(), CLI_ENTRY, "zread", *cli_args, "-f", "json"]
    try:
        proc = subprocess.run(cmd, cwd=CLI_CWD, capture_output=True, timeout=REQUEST_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"请求超时（>{REQUEST_TIMEOUT}s）：opencli {' '.join(cli_args)}")
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0 or not out:
        raise RuntimeError(err or out or f"exit code {proc.returncode}")
    # stdout 可能混入提示行（如 update notice），定位 JSON 数组起点
    starts = [i for i in (out.find("["), out.find("{")) if i >= 0]
    if not starts:
        raise RuntimeError(f"输出中未找到 JSON：{out[:300]}")
    return json.loads(out[min(starts):])


def run_cli_retry(cli_args: list) -> list:
    last_err = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return run_cli(cli_args)
        except RuntimeError as e:
            last_err = e
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_WAIT)
    raise last_err


def normalize_repo(raw: str) -> str:
    """接受 owner/name 或 zread.ai URL，统一成 owner/name。"""
    v = raw.strip().rstrip("/")
    v = re.sub(r"^https?://(www\.)?zread\.ai/", "", v, flags=re.I)
    parts = [p for p in v.split("/") if p]
    if len(parts) != 2:
        sys.exit(f"[错误] repo 需要是 owner/name 形式，例如 pymupdf/PyMuPDF，收到：{raw}")
    return "/".join(parts)


def fetch_page_list(repo: str, lang: str) -> list:
    args = ["read", repo, "--list"]
    if lang:
        args += ["--lang", lang]
    return run_cli_retry(args)


def fetch_page_by_slug(repo: str, slug: str, lang: str) -> dict:
    args = ["read", repo, "--slug", slug]
    if lang:
        args += ["--lang", lang]
    rows = run_cli_retry(args)
    return rows[0] if rows else {}


def fetch_page_by_number(repo: str, page: int, lang: str) -> dict:
    args = ["read", repo, "--page", str(page)]
    if lang:
        args += ["--lang", lang]
    rows = run_cli_retry(args)
    return rows[0] if rows else {}


def sanitize(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name).strip("_") or "repo"


def build_markdown(repo: str, lang: str, rows: list) -> str:
    lines = [
        "---",
        f"source: https://zread.ai/{repo}",
        f"repo: {repo}",
        f"fetched: {date.today().isoformat()}",
        f"pages: {len(rows)}",
    ]
    if lang:
        lines.append(f"lang: {lang}")
    lines += ["---", "", f"# {repo} — zread.ai 解读", ""]
    for row in rows:
        section = f"（{row['section']}）" if row.get("section") else ""
        lines += [f"## {row['page']}. {row['topic']}{section}", "", row["content"], "", "---", ""]
    return "\n".join(lines)


def save_markdown(repo: str, lang: str, md: str, save_dir: str) -> Path:
    out_dir = Path(save_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    owner, name = repo.split("/")
    suffix = f"_{lang}" if lang else ""
    path = out_dir / f"{sanitize(owner)}_{sanitize(name)}_zread{suffix}.md"
    path.write_text(md, encoding="utf-8")
    return path


def main():
    # Windows 控制台中文/特殊字符防崩
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(
        description="读取仓库的 zread.ai AI 解读 wiki（经 opencli-upstream 的 zread read 适配器）")
    ap.add_argument("--repo", required=True, help="owner/name 或 zread.ai URL")
    ap.add_argument("--page", type=int, default=1, help="页码（对应 slug 前缀，默认 1=概述）")
    ap.add_argument("--slug", default="", help="精确 slug（优先于 --page）")
    ap.add_argument("--lang", default="", help="语言标签，如 zh / zh-CN / en（zread 按语言生成不同 wiki）")
    ap.add_argument("--list", action="store_true", help="只列出全部页面目录")
    ap.add_argument("--all", action="store_true", help="读取全部页面（建议配合 --save）")
    ap.add_argument("--save", default="", help="保存 markdown 的目录（省略则打印到屏幕）")
    args = ap.parse_args()

    repo = normalize_repo(args.repo)

    # 模式一：--list 只看目录
    if args.list:
        pages = fetch_page_list(repo, args.lang)
        print(f"{repo} 共 {len(pages)} 页：")
        for r in pages:
            print(f"  {str(r['page']):>3}. {r['topic']:<32} [{r.get('section', '')}]  slug={r['content']}")
        return

    # 模式二：--all 读全部页面
    if args.all:
        pages = fetch_page_list(repo, args.lang)
        pages = sorted(pages, key=lambda r: int(r["page"]) if str(r["page"]).isdigit() else 999)
        collected = []
        for i, r in enumerate(pages, 1):
            print(f"[{i}/{len(pages)}] 读取 {r['content']}（{r['topic']}）…", flush=True)
            row = fetch_page_by_slug(repo, r["content"], args.lang)
            collected.append(row)
        md = build_markdown(repo, args.lang, collected)
        if args.save:
            path = save_markdown(repo, args.lang, md, args.save)
            print(f"[完成] {len(collected)} 页已保存 → {path}")
        else:
            print(md)
        return

    # 模式三：单页（--slug 优先，否则 --page）
    if args.slug:
        row = fetch_page_by_slug(repo, args.slug, args.lang)
    else:
        row = fetch_page_by_number(repo, args.page, args.lang)
    if not row:
        sys.exit("[错误] 未读到内容")

    if args.save:
        md = build_markdown(repo, args.lang, [row])
        path = save_markdown(repo, args.lang, md, args.save)
        print(f"[完成] 已保存 → {path}")
    else:
        section = f"（{row['section']}）" if row.get("section") else ""
        print(f"# {row['page']}. {row['topic']}{section}\n")
        print(row["content"])


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        sys.exit(1)
