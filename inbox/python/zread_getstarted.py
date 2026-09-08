# -*- coding: utf-8 -*-
"""zread Get Started 采集

弹窗输入 repo → 拉取 zread.ai 的 Get Started 分区（中文 wiki）→ 每项目一个目录存入 Obsidian。

底层复用 zread_read.py 的 CLI 调用（opencli-upstream 的 zread read，纯 HTTP，无需浏览器）。
固定参数：--lang zh、Get Started 分区（zread 固定模板的第 1-3 页：Overview / Quick Start / 入门主题）。

输出结构：
    05_long_project/zread/{owner}_{name}/
        00_目录.md      # 全部页面目录（Get Started 双链本地文件，其余仅列出）
        {slug}.md       # Get Started 每页一个笔记（如 1-overview.md）

用法：
    python zread_getstarted.py              # 弹窗输入 repo
    python zread_getstarted.py owner/name   # 命令行指定（tkinter 不可用时的回退）
"""
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from zread_read import (  # noqa: E402
    fetch_page_by_slug,
    fetch_page_list,
    normalize_repo,
    run_cli_retry,
    sanitize,
)

OUTPUT_ROOT = Path("d:/obsidian/demo/05_long_project/zread")
LANG = "zh"
PAGE_GAP = (2, 4)  # 逐页请求间隔（秒），轻量防限流


def ask_repo_dialog():
    """tkinter 弹窗输入 repo；取消/不可用时返回 None。"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    repo = simpledialog.askstring(
        "zread Get Started",
        "GitHub repo（owner/name 或 zread.ai URL）：\n例如 pymupdf/PyMuPDF",
        parent=root,
    )
    root.destroy()
    return repo


def notify(title, message):
    """有 tkinter 时弹窗提示结果，否则打印。"""
    print(f"{title}: {message}")
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        return
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showinfo(title, message, parent=root)
    root.destroy()


def page_num(row, fallback):
    raw = str(row.get("page", ""))
    return int(raw) if raw.isdigit() else fallback


def write_catalog(out_dir: Path, repo: str, pages: list, fetched_slugs: set, failed_slugs: list):
    """00_目录.md：全部页面表格；Get Started 行内链本地笔记，其余标注未拉取。"""
    lines = [
        "---",
        f"source: https://zread.ai/{repo}",
        f"repo: {repo}",
        f"pages: {len(pages)}",
        f"get_started: {len(fetched_slugs)}",
        f"lang: {LANG}",
        f"fetched: {date.today().isoformat()}",
        "---",
        "",
        f"# {repo} — zread.ai 解读目录",
        "",
        "> 已拉取 Get Started 分区到本目录；其余分区（Buzz / Deep Dive）如需全量：",
        f"> `python zread_read.py --repo {repo} --all --lang {LANG} --save <目录>`",
        "",
        "| # | 主题 | 分区 | 本地笔记 |",
        "|---|------|------|----------|",
    ]
    ordered = sorted(enumerate(pages, 1), key=lambda t: page_num(t[1], t[0]))
    for _, p in ordered:
        slug = str(p.get("content", ""))
        section = str(p.get("section", ""))
        link = f"[[{sanitize(slug)}]]" if slug in fetched_slugs else "—"
        lines.append(f"| {p.get('page', '')} | {p.get('topic', '')} | {section} | {link} |")
    lines.append("")
    if failed_slugs:
        lines.append(f"> [!warning] 获取失败（重跑可补）：{', '.join(failed_slugs)}")
        lines.append("")
    path = out_dir / "00_目录.md"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    repo_raw = sys.argv[1] if len(sys.argv) > 1 else ask_repo_dialog()
    if not repo_raw or not repo_raw.strip():
        sys.exit("[错误] 未提供 repo（弹窗输入或命令行参数 owner/name）")
    repo = normalize_repo(repo_raw)

    # 1. 目录（--list，固定中文）
    pages = fetch_page_list(repo, LANG)
    ordered = sorted(enumerate(pages, 1), key=lambda t: page_num(t[1], t[0]))
    gs_pages = [p for _, p in ordered
                if str(p.get("section", "")).strip().lower() == "get started"]
    if not gs_pages:
        sys.exit(f"[错误] {repo} 的 wiki 中没有 Get Started 分区页面（共 {len(pages)} 页）")
    print(f"{repo} 共 {len(pages)} 页，其中 Get Started {len(gs_pages)} 页："
          + "、".join(str(p['topic']) for p in gs_pages))

    # 2. 每项目一个目录
    owner, name = repo.split("/")
    out_dir = OUTPUT_ROOT / f"{sanitize(owner)}_{sanitize(name)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 3. 逐页拉取（已存在跳过 → 重复运行幂等；失败跳过不中断）
    fetched, failed = set(), []
    for i, p in enumerate(gs_pages, 1):
        slug = str(p["content"])
        path = out_dir / f"{sanitize(slug)}.md"
        if path.exists():
            fetched.add(slug)
            print(f"[{i}/{len(gs_pages)}] {slug} 已存在，跳过")
            continue
        print(f"[{i}/{len(gs_pages)}] 读取 {slug}（{p['topic']}）…")
        try:
            row = fetch_page_by_slug(repo, slug, LANG)
            body = str(row.get("content", ""))
            note = [
                "---",
                f"source: https://zread.ai/{repo}/{slug}",
                f"repo: {repo}",
                f"page: {row.get('page', p.get('page', ''))}",
                f"topic: {row.get('topic', '')}",
                f"section: {row.get('section', '')}",
                f"lang: {LANG}",
                f"fetched: {date.today().isoformat()}",
                "---",
                "",
                f"## {row.get('page', '')}. {row.get('topic', '')}",
                "",
                body,
                "",
            ]
            path.write_text("\n".join(note), encoding="utf-8", newline="\n")
            fetched.add(slug)
        except RuntimeError as e:
            failed.append(slug)
            print(f"    ⚠ 失败（跳过继续）：{e}")
        if i < len(gs_pages):
            time.sleep(PAGE_GAP[0] + (PAGE_GAP[1] - PAGE_GAP[0]) * (i % 2))

    # 4. 目录文件（最后写，保证只含实际成功的页）
    write_catalog(out_dir, repo, pages, fetched, failed)

    msg = (f"Get Started {len(fetched)}/{len(gs_pages)} 页 → {out_dir}")
    if failed:
        msg += f"\n失败 {len(failed)} 页：{', '.join(failed)}（重跑同一命令可补）"
    notify("zread Get Started 完成", msg)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as e:
        notify("zread Get Started 失败", str(e))
        sys.exit(1)
