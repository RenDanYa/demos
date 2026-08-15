# -*- coding: utf-8 -*-
"""按项目主题分类 IT咖啡馆汇总笔记中的项目

解析 IT咖啡馆-视频简介汇总.md,
将 ## 项目地址 模块中的每个项目拆分出来,
根据项目名称和描述按主题分类,
生成分类汇总笔记。

用法:
    python itcafe_classify.py
"""
import re
from collections import defaultdict
from pathlib import Path

SUMMARY_FILE = Path("d:/obsidian/视频/resource/IT咖啡馆-视频简介汇总.md")
OUTPUT_FILE = Path("d:/obsidian/视频/resource/IT咖啡馆-项目分类汇总.md")


# ============ 分类规则 (关键词 → 分类) ============
# 按优先级顺序匹配, 先匹配到的分类优先
CATEGORY_RULES = [
    ("AI Agent 与 MCP 生态", [
        "agent", "mcp", "skill", "claude code", "openclaw",
        "clawdbot", "autoglm", "manus", "multi-agent", "多智能体",
        "智能体", "agent记忆", "agent框架", "agent工作台", "agent技能",
        "a2a协议", "agent开发", "agent系统", "agent平台",
        "上下文压缩", "context compress", "agent省token", "agent联网",
        "代码库记忆", "agent视频", "agent事务所", "生产级agent",
    ]),
    ("大语言模型", [
        "deepseek", "qwen", "通义千问", "glm", "gpt-", "gpt5", "kimi",
        "llama", "grok", "大模型", "大语言模型", "推理模型", "多模态模型",
        "语言模型", "llm", "微调", "fine-tun", "r1", "janus",
        "千问", "智谱", "mini-max", "minimax", "世界模型", "world model",
        "物理ai", "物理ai世界", "推理框架", "推理加速",
    ]),
    ("AI 编程与代码工具", [
        "cursor", "copilot", "vscode", "ide", "编程助手", "代码助手",
        "ai编程", "ai coding", "code agent", "编程智能体", "codegen",
        "代码生成", "代码审查", "屎山代码", "代码图谱", "代码库",
        "vibe coding", "terminal编程", "终端编程", "编程工具",
    ]),
    ("AI 多媒体生成", [
        "视频生成", "文生视频", "video generation", "sora", "动画生成",
        "图像生成", "文生图", "flux", "stable diffusion", "绘图模型",
        "ai画", "图片生成", "卡通", "数字人", "换脸", "视频换脸",
        "声音克隆", "tts", "语音合成", "文生语音", "s2v", "音乐生成",
        "3d生成", "3d重建", "3d模型", "物理引擎", "剪辑", "剪辑工具",
        "写html出视频", "视频模型", "音视频", "语音活动检测",
        "语音转文字", "实时语音", "asr", "说话人",
    ]),
    ("AI 应用与 RAG", [
        "ocr", "文档解析", "pdf解析", "pdf分类", "文档检索", "rag",
        "知识图谱", "向量数据库", "embedding", "ai助手", "ai搜索",
        "ai搜索引擎", "深度研究", "ai问答", "对话", "chatgpt",
        "ai理财", "情绪", "ai求职", "ai面试", "会议助手", "ai会议",
        "ai私教", "个性化", "ai教育", "客服", "舆情分析",
        "数据查询", "ai桌宠", "桌面ai",
    ]),
    ("开发工具与 CLI", [
        "cli", "命令行", "终端", "shell", "terminal", "bash",
        "zsh", "fish", "tmux", "开发脚手架", "脚手架", "框架",
        "sdk", "api调试", "postman", "insomnia", "api工具",
        "git客户端", "json可视", "正则", "devtools", "设计工具",
        "office文档", "文档cli", "文本编辑器", "编辑器",
        "换行工具", "排版", "架构图",
    ]),
    ("Web 前端与 UI", [
        "react", "vue", "nextjs", "next.js", "css", "tailwind",
        "ui库", "ui组件", "前端", "frontend", "web 3d", "web3d",
        "动画库", "canvas", "图表", "dashboard", "白板",
        "画布", "低代码", "网页变app", "前端动画", "3d引擎",
        "javascript 3d", "web 3d引擎", "ui元素",
    ]),
    ("基础设施与 DevOps", [
        "docker", "容器", "kubernetes", "k8s", "devops",
        "ci/cd", "部署", "deploy", "paas", "云原生",
        "serverless", "微服务", "虚拟机", "vm",
        "launchpad", "自托管", "self-host", "本地aws",
        "备份", "docker中运行",
    ]),
    ("数据库与存储", [
        "数据库", "database", "sql", "sqlite", "mysql",
        "postgres", "redis", "mongodb", "bi工具", "数据可视化",
        "对象存储", "oss", "存储", "storage", "文件系统",
        "数据平台", "数据工程", "分析数据库", "轻量数据库",
    ]),
    ("安全与渗透测试", [
        "安全", "security", "渗透测试", "penetration", "pentest",
        "waf", "防火墙", "黑客", "hacking", "漏洞",
        "密钥", "key management", "加密", "crypto",
        "身份认证", "auth", "零知识", "情报搜索", "网络安全",
        "密钥检测", "安全扫描", "换脸检测",
    ]),
    ("自动化与工作流", [
        "n8n", "工作流", "workflow", "自动化", "automation",
        "编排", "orchestrat", "rpa", "任务管理", "工作流编排",
        "流程自动化",
    ]),
    ("网络与监控", [
        "监控", "monitor", "网络管理", "network",
        "服务器管理", "服务器", "nginx", "reverse proxy",
        "代理", "proxy", "vpn", "dns", "iptv", "网盘",
        "蓝牙", "文件传输", "文件分享", "airdrop", "localsend",
        "网络扫描", "绿墙",
    ]),
    ("知识管理与笔记", [
        "notion", "obsidian", "笔记", "知识库", "知识管理",
        "wiki", "markdown", "文档工具", "pkm", "第二大脑",
        "信息仪表盘", "信息浏览器", "个人图书馆",
    ]),
    ("实用工具与效率", [
        "翻译", "translate", "录屏", "截图", "下载器", "下载工具",
        "浏览器", "browser", "窗口管理", "菜单栏", "桌面",
        "清理", "卸载", "优化", "工具箱", "工具集",
        "百宝箱", "瑞士军刀", "效率", "番茄钟", "图片编辑",
        "图像编辑", "photo", "gimp", "photoshop", "音频工具",
        "音乐", "聊天", "聊天应用", "社媒", "理财应用",
        "网盘搜索", "问卷", "桌面宠物", "桌宠", "天气",
        "稍后再读", "文件传输工具", "快捷", "定制",
    ]),
    ("游戏与娱乐", [
        "游戏", "game", "游戏引擎", "红警", "我的世界",
        "minecraft", "godot", "游戏开发", "sdk",
    ]),
    ("硬件与设备", [
        "显示器", "mac mini", "macmini", "硬件", "gpu",
        "npu", "ai pc", "aibook", "机器人", "robot",
        "机械臂", "智能镜子", "可穿戴", "摩尔线程",
    ]),
    ("金融与商业", [
        "量化", "quant", "交易", "trading", "股票",
        "金融", "finance", "理财", "投资", "电商",
        "ecommerce", "crm", "erp", "hr系统", "营销",
        "发票", "电子签", "金融交易", "股票分析",
    ]),
    ("学习与教育资源", [
        "教程", "学习", "课程", "电子书", "ebook",
        "编程书", "面试", "求职", "考试", "公考",
        "awesome", "资源汇总", "资源清单", "指南",
        "计算机科学", "算法", "数据结构", "免费服务",
        "free-for-dev", "开发者资源", "从零", "工程",
        "登月", "历史", "实践", "数据集", "dataset",
        "微软课程", "aigc课程", "计算机指南",
    ]),
]


def classify_project(name, desc):
    """根据项目名称和描述返回分类"""
    text = f"{name} {desc}".lower()
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.lower() in text:
                return category
    return "其他"


def parse_summary():
    """解析汇总笔记, 提取每个条目的项目

    返回: list of dict, 每个 dict 含:
        - source: 来源视频标题
        - pub_time: 发布时间
        - url: 视频链接
        - projects: [(name, link, desc), ...]
    """
    content = SUMMARY_FILE.read_text(encoding="utf-8")

    # 按 ### 分割条目
    entries = re.split(r'^### \d+\. ', content, flags=re.MULTILINE)[1:]

    results = []
    for entry in entries:
        lines = entry.strip().split("\n")

        # 第一行是标题
        title = lines[0].strip()

        # 提取发布时间和链接
        pub_time = ""
        url = ""
        body_start = 0
        for i, line in enumerate(lines[1:], 1):
            m = re.match(r'- 发布时间:\s*(.+)', line)
            if m:
                pub_time = m.group(1).strip()
            m = re.match(r'- 视频链接:\s*(.+)', line)
            if m:
                url = m.group(1).strip()
            if line.startswith("**##"):
                body_start = i
                break

        if body_start == 0:
            continue

        # 提取项目地址内容
        body = "\n".join(lines[body_start + 1:])

        # 查找项目地址内容块 (到 --- 为止)
        body = re.split(r'\n---\s*$', body)[0].strip()

        # 去掉开头的 ** 和 ## 标记
        body = re.sub(r'^\**\s*##\s*项目地址\s*\**\s*', '', body)
        body = re.sub(r'^\**\s*##\s*视频简介\s*\**\s*', '', body)

        results.append({
            "title": title,
            "pub_time": pub_time,
            "url": url,
            "body": body,
        })

    return results


def extract_projects(body):
    """从项目地址内容中提取单个项目

    支持格式:
    1. "数字、项目名称：xxx - 描述\nGitHub 链接：xxx"
    2. "数字、项目名称：xxx - 描述\nHuggingFace 链接：xxx"
    3. "#数字\n项目名称：xxx\nGitHub 链接：xxx"
    4. "项目名称：xxx GitHub 链接：xxx" (单行)

    返回: list of (name, link, desc)
    """
    projects = []

    # 检测是否包含项目地址格式 (必须有 "项目名称" 关键词)
    if "项目名称" not in body:
        return projects

    # 用 "项目名称" 作为分隔点
    parts = re.split(r'项目名称[：:]\s*', body)

    for part in parts[1:]:
        part = part.strip()
        if not part:
            continue

        # 第一行是项目名称 (可能包含描述, 用 " - " 分隔)
        first_line = part.split('\n')[0].strip()

        # 分离名称和描述
        if ' - ' in first_line:
            name, desc = first_line.split(' - ', 1)
            name = name.strip()
            desc = desc.strip()
        elif ' – ' in first_line:
            name, desc = first_line.split(' – ', 1)
            name = name.strip()
            desc = desc.strip()
        else:
            name = first_line
            desc = ""

        # 清理名称和描述中残留的 "GitHub 链接" 文本
        name = re.sub(r'\s*GitHub\s*链接[：:].*$', '', name).strip()
        desc = re.sub(r'\s*GitHub\s*链接[：:].*$', '', desc).strip()
        desc = re.sub(r'\s*HuggingFace\s*链接[：:].*$', '', desc).strip()

        # 清理名称中的编号前缀 (如 "1、")
        name = re.sub(r'^\d+[、.．]\s*', '', name).strip()

        # 查找链接 (GitHub 或 HuggingFace)
        link = ""
        link_match = re.search(r'(?:GitHub|HuggingFace|Gitee)\s*链接[：:]\s*(\S+)', part)
        if link_match:
            link = link_match.group(1).strip().rstrip(',')

        # 如果描述为空, 尝试从名称行之后的行提取
        if not desc:
            lines_after = part.split('\n')[1:]
            for line in lines_after:
                line = line.strip()
                if line and not re.match(r'(?:GitHub|HuggingFace|Gitee)\s*链接', line):
                    desc = line
                    break

        # 限制描述长度
        if len(desc) > 150:
            desc = desc[:150] + "..."
        desc = re.sub(r'\s+', ' ', desc).strip(' -–—')

        if name and len(name) > 1:
            projects.append((name, link, desc))

    return projects


def main():
    entries = parse_summary()
    print(f"解析条目数: {len(entries)}")

    # 收集所有项目
    all_projects = []
    project_only = 0
    summary_only = 0

    for entry in entries:
        projects = extract_projects(entry["body"])
        if projects:
            project_only += 1
            for name, link, desc in projects:
                category = classify_project(name, desc)
                all_projects.append({
                    "name": name,
                    "link": link,
                    "desc": desc,
                    "category": category,
                    "source": entry["title"],
                    "pub_time": entry["pub_time"],
                    "url": entry["url"],
                })
        else:
            # 视频简介类, 整体作为一个条目
            summary_only += 1
            body = entry["body"].strip()
            if len(body) > 150:
                body = body[:150] + "..."
            category = classify_project(entry["title"], body)
            all_projects.append({
                "name": entry["title"],
                "link": entry["url"],
                "desc": body,
                "category": category,
                "source": entry["title"],
                "pub_time": entry["pub_time"],
                "url": entry["url"],
            })

    print(f"项目地址类条目: {project_only}")
    print(f"视频简介类条目: {summary_only}")
    print(f"总项目/条目数: {len(all_projects)}")

    # 按分类分组
    by_category = defaultdict(list)
    for p in all_projects:
        by_category[p["category"]].append(p)

    # 统计分类
    print("\n分类统计:")
    for cat in sorted(by_category.keys(), key=lambda c: -len(by_category[c])):
        print(f"  {cat}: {len(by_category[cat])}")

    # 生成分类汇总笔记
    lines = []
    lines.append("---")
    lines.append("title: IT咖啡馆项目分类汇总")
    lines.append("创建时间: 2026-08-15")
    lines.append(f"总项目数: {len(all_projects)}")
    lines.append(f"分类数: {len(by_category)}")
    lines.append("---")
    lines.append("")
    lines.append("# IT咖啡馆项目分类汇总")
    lines.append("")
    lines.append(f"共整理 **{len(all_projects)}** 个项目/条目, 按 **{len(by_category)}** 个主题分类。")
    lines.append("")

    # 分类目录
    lines.append("## 分类目录")
    lines.append("")
    for cat in sorted(by_category.keys(), key=lambda c: -len(by_category[c])):
        count = len(by_category[cat])
        anchor = cat.replace(" ", "-").replace("/", "")
        lines.append(f"- [{cat}](#{anchor}) ({count})")
    lines.append("")

    # 各分类详情
    lines.append("## 分类详情")
    lines.append("")
    for cat in sorted(by_category.keys(), key=lambda c: -len(by_category[c])):
        projects = by_category[cat]
        lines.append(f"### {cat} ({len(projects)})")
        lines.append("")

        # 按发布时间排序
        projects.sort(key=lambda p: p["pub_time"], reverse=True)

        for p in projects:
            lines.append(f"- **{p['name']}**")
            if p["desc"]:
                lines.append(f"  - {p['desc']}")
            if p["link"] and p["link"].startswith("http"):
                lines.append(f"  - 链接: {p['link']}")
            if p["source"] != p["name"]:
                lines.append(f"  - 来源: {p['source']} ({p['pub_time'][:10]})")
            lines.append("")

        lines.append("---")
        lines.append("")

    output = "\n".join(lines)
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(f"\n已生成分类汇总: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
