# -*- coding: utf-8 -*-
"""小红书点点 AI 问答采集

调用 opencli xiaohongshu search-ai 命令, 把 AI 回答保存为 Obsidian Markdown。

用法:
    python xiaohongshu_ai.py             # 弹窗输入关键词
    python xiaohongshu_ai.py "婚前多久试婚纱"
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# 复用 xiaohongshu_collect 的工具函数
sys.path.insert(0, str(Path(__file__).parent))
from xiaohongshu_collect import (  # noqa: E402
    OPENCLI_CMD,
    OUTPUT_ROOT,
    log,
    run_opencli,
    show_input_dialog,
    sanitize_filename,
)

# ============ 配置 ============
AI_OUTPUT_ROOT = OUTPUT_ROOT / "AI问答"
TIMEOUT_AI = 60  # search-ai 默认 --timeout 20, 加上页面加载冗余


def show_ai_input_dialog():
    """tkinter 弹窗: 关键词 (单独实现, 不需要 limit)"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        # 回退到命令行
        if len(sys.argv) >= 2:
            return sys.argv[1].strip()
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    kw = simpledialog.askstring(
        "小红书点点 AI",
        "请输入问题关键词:",
        initialvalue="婚前多久试婚纱",
        parent=root,
    )
    root.destroy()
    return kw.strip() if kw else None


def call_search_ai(query, timeout=20, debug=False):
    """调用 opencli xiaohongshu search-ai 命令

    返回: [{section, content}, ...] 或 None (失败时)
    """
    args = ["xiaohongshu", "search-ai", query, "-f", "json", "--timeout", str(timeout)]
    if debug:
        args.append("--debug")
        args.append("true")

    ok, stdout, err = run_opencli(args, TIMEOUT_AI)
    if not ok:
        log(f"search-ai 调用失败: {err}")
        return None

    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "sections" in data:
            return data["sections"]
    except json.JSONDecodeError as e:
        log(f"search-ai JSON 解析失败: {e}")
        log(f"原始 stdout 前 300 字符: {stdout[:300] if stdout else '(空)'}")
    return None


def build_markdown(query, sections):
    """生成 markdown 内容

    sections: [{section, content}, ...]
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_title = re.sub(r"[\r\n]+", " ", query)[:50]

    lines = [
        "---",
        "tags: [小红书, 点点AI, AI问答]",
        f'title: "AI问答 - {safe_title}"',
        f"query: {json.dumps(query, ensure_ascii=False)}",
        f"createTime: {datetime.now().isoformat(timespec='seconds')}",
        "status: 已采集",
        "---",
        "",
        f"# AI问答 - {query}",
        "",
        f"> **提问时间**: {now}",
        f"> **来源**: 小红书点点 AI",
        "",
    ]

    if not sections:
        lines.append("> [!warning] 未获取到 AI 回答")
        lines.append(">")
        lines.append("> 可能原因: 登录态过期、风控、AI 正在生成中。请稍后重试。")
        return "\n".join(lines) + "\n"

    def format_section_content(content):
        """section 内容格式化: 多行(每行独立要点)转为无序列表, 单行保持段落"""
        nonempty = [cl for cl in content.split("\n") if cl.strip()]
        if len(nonempty) <= 1:
            # 单行段落, 保持原样
            return [f"> {nonempty[0]}"] if nonempty else []
        # 多行 — 每行作为列表项 (Obsidian callout 内 "> - item" 渲染为列表)
        return [f"> - {cl}" for cl in nonempty]

    # 所有 section 合并到一个 callout (避免多个 callout 之间空行断裂, 阅读更连贯)
    # 单 section: callout 标题用 section 名
    # 多 section: callout 标题用主标题, 每个 section 用加粗子标题分隔
    if len(sections) == 1:
        sec = sections[0]
        title = sec.get("section") or "回答"
        content = sec.get("content") or ""
        lines.append(f"> [!ai] {title}")
        lines.append(">")
        lines.extend(format_section_content(content))
        lines.append("")
        return "\n".join(lines) + "\n"

    # 多 section: 单个 callout, section 标题用 **加粗** 子标题, 内容紧随其后
    lines.append("> [!ai] AI 回答")
    lines.append(">")
    for sec in sections:
        title = sec.get("section") or ""
        content = sec.get("content") or ""
        if not title and not content:
            continue
        if title:
            lines.append(f"> **{title}**")
            lines.append(">")
        lines.extend(format_section_content(content))
        lines.append(">")

    return "\n".join(lines) + "\n"


def write_markdown(query, md_content):
    """保存 markdown 文件, 返回路径"""
    AI_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # 文件名用关键词 (清理后)
    safe_name = sanitize_filename(query)[:60] or "untitled"
    md_path = AI_OUTPUT_ROOT / f"{safe_name}.md"

    # 同名文件已存在时, 加时间戳后缀避免覆盖
    if md_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        md_path = AI_OUTPUT_ROOT / f"{safe_name}_{ts}.md"

    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def main():
    log("=" * 60)
    log("小红书点点 AI 问答采集 启动")
    log(f"OPENCLI_CMD: {OPENCLI_CMD}")
    log(f"输出目录: {AI_OUTPUT_ROOT}")
    log("=" * 60)

    # 1. 获取关键词
    query = None
    if len(sys.argv) >= 2:
        query = sys.argv[1].strip()
    else:
        query = show_ai_input_dialog()

    if not query:
        log("未输入关键词, 退出")
        return 1

    log(f"问题: {query}")

    # 2. 调用 search-ai
    log("调用 search-ai 中, 请稍候 (约 30-60 秒)...")
    sections = call_search_ai(query, timeout=30)

    if not sections:
        log("AI 未返回内容, 尝试带 --debug 重试一次...")
        sections = call_search_ai(query, timeout=40, debug=True)
        # debug 模式会返回调试信息而非内容, 失败则退出
        if not sections:
            log("重试仍失败, 退出")
            return 2

    # 过滤掉调试行 (section 以 _ 开头)
    real_sections = [s for s in sections if not str(s.get("section", "")).startswith("_")]
    if not real_sections:
        # 全是调试行, 当作失败
        log(f"仅得到调试信息, 退出: {sections}")
        return 3

    log(f"获取到 {len(real_sections)} 个 section")

    # 3. 生成 markdown
    md_content = build_markdown(query, real_sections)
    md_path = write_markdown(query, md_content)
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
