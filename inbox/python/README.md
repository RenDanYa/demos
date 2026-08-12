# Obsidian 数据采集工具集

基于 [opencli](https://github.com/jackwener/opencli) 的 Obsidian 数据采集脚本集合，覆盖小红书、BOSS直聘、B站、拼多多、GitHub 五个平台。

所有脚本输出到 `d:/obsidian/demo/05_long_project/` 下对应子目录，日志写入 `05_long_project/程序运行日志/`。

## 目录

| 平台 | 脚本 | 用途 |
|------|------|------|
| 小红书 | `xiaohongshu_collect.py` | 关键词搜索批量采集 |
| 小红书 | `xiaohongshu_note.py` | 单篇笔记采集 |
| 小红书 | `xiaohongshu_user.py` | 博主主页笔记采集 |
| 小红书 | `xiaohongshu_ai.py` | 点点 AI 问答采集 |
| 小红书 | `xiaohongshu_ai_batch.py` | AI 问答批量采集 |
| BOSS直聘 | `boss_search.py` | 职位搜索采集 |
| BOSS直聘 | `boss_resume.py` | 详情断点续传 |
| BOSS直聘 | `boss_fix_status.py` | 修复采集状态 |
| B站 | `bilibili_following.py` | 关注列表采集 |
| B站 | `bilibili_videos.py` | 关注博主视频采集 |
| B站 | `bilibili_weekly.py` | 每周必看采集 |
| B站 | `bilibili_weekly_batch.py` | 每周必看批量采集 |
| B站 | `bilibili_weekly_by_partition.py` | 每周必看按分区归档 |
| GitHub | `github_trending.py` | Trending 仓库采集 |
| GitHub | `github_topic.py` | Topic 仓库采集 |
| 拼多多 | `pdd_search.py` | 商品搜索（综合排序） |
| 拼多多 | `pdd_search_cheap.py` | 商品搜索（价格升序） |
| 拼多多 | `pdd_search_batch.py` | 批量低价搜索 |
| 拼多多 | `pdd_search_batch_default.py` | 批量综合搜索 |

## 前置依赖

### 环境要求

- Python 3.10+
- Windows（脚本使用 tkinter 弹窗、ctypes 防睡眠、taskkill 进程管理）
- [opencli](https://github.com/jackwener/opencli) 已安装并配置浏览器桥接

### opencli 调用方式

脚本通过 `subprocess` 调用 opencli 的 Node.js 入口，绕过 `cmd.exe` 避免 URL 中 `&` 字符的命令分隔问题：

```python
OPENCLI_CMD = ("node", "d:/voice/opencli-main/dist/main.js")
```

该配置定义在 `xiaohongshu_collect.py` 的 `_resolve_opencli()` 中，所有脚本共享。若 opencli 安装路径不同，修改此函数即可。

### 输出目录结构

```
d:/obsidian/demo/
├── inbox/
│   ├── python/              # 脚本目录
│   ├── 附件/                # 图片下载目录
│   ├── 问题清单.md           # AI 批量问答的输入清单
│   └── 商品购买清单.md       # 拼多多批量搜索的输入清单
├── 05_long_project/
│   ├── 小红书/              # 小红书采集输出
│   ├── BOSS直聘/            # BOSS直聘采集输出
│   ├── B站关注/             # B站关注采集输出
│   ├── B站/                 # B站每周必看采集输出
│   │   ├── 每周必看/        # 单期笔记 (weekly_{期数}.md)
│   │   │   └── 分区/        # 按分区归档 (人文历史.md 等)
│   ├── GitHub/              # GitHub 采集输出
│   │   ├── Trending/        # Trending 仓库
│   │   └── Topic/           # Topic 仓库
│   ├── 拼多多/              # 拼多多采集输出
│   └── 程序运行日志/         # 每次运行的独立日志
```

## 核心模块：xiaohongshu_collect.py

这是整个工具集的**基础模块**，其他脚本通过 `sys.path.insert` 导入其中的共享函数和配置。

### 导出的关键符号

| 类别 | 符号 | 说明 |
|------|------|------|
| 配置 | `OPENCLI_CMD` | opencli 调用命令元组 |
| 配置 | `OBSIDIAN_ROOT` | Obsidian 根目录 `d:/obsidian/demo` |
| 配置 | `OUTPUT_ROOT` | 小红书输出目录 |
| 配置 | `IMAGES_ROOT` | 图片附件目录 |
| 配置 | `LOG_DIR` | 日志目录 |
| 工具 | `log(msg)` | 统一日志（console + 文件，UTF-8 安全） |
| 工具 | `run_opencli(args, timeout)` | 调用 opencli，返回 `(success, stdout, stderr)` |
| 工具 | `sanitize_filename(name)` | 清洗 Windows 非法文件名字符 |
| 采集 | `get_note_full(note_id, ...)` | 获取笔记详情（正文+评论+媒体） |
| 采集 | `download_images(...)` | 下载图片到附件目录 |
| 渲染 | `build_markdown(...)` | 生成 Obsidian Markdown |
| 防风控 | `INTERVAL_MIN/MAX` | 请求间隔 5-8 秒 |
| 防风控 | `BATCH_SIZE` | 每 50 条批次休息 |
| 防风控 | `FAIL_THRESHOLD` | 连续 3 次失败暂停 |

### 防风控策略

所有采集脚本共享以下防风控机制：

- **请求间隔**：每次请求间随机等待 5-8 秒（不同平台可能调整）
- **批次暂停**：每 N 条记录暂停休息 30-60 秒
- **连续失败冷却**：连续失败达到阈值后长等待 60-120 秒
- **重试机制**：单条失败重试 2 次，间隔 20-30 秒
- **心跳日志**：长睡眠期间每 10 秒输出心跳，防止父进程误判卡死

---

## 小红书系列

### xiaohongshu_collect.py — 关键词搜索批量采集

搜索小红书笔记，批量获取正文、评论、图片，保存为 Obsidian Markdown。

```bash
python xiaohongshu_collect.py                    # 弹窗输入关键词 + 数量
python xiaohongshu_collect.py "obsidian"         # 默认采集 10 条
python xiaohongshu_collect.py "obsidian" 20      # 指定数量
```

输出到 `05_long_project/小红书/{关键词}/` 目录，每条笔记一个 `.md` 文件，图片下载到 `inbox/附件/`。

### xiaohongshu_note.py — 单篇笔记采集

输入笔记 URL，采集单篇笔记的完整内容。

```bash
python xiaohongshu_note.py                        # 弹窗输入 URL
python xiaohongshu_note.py "https://www.xiaohongshu.com/explore/xxx?xsec_token=..."
```

输出到 `05_long_project/小红书/` 根目录（不建子文件夹）。

### xiaohongshu_user.py — 博主主页笔记采集

输入博主主页 URL，批量采集其发布的笔记。

```bash
python xiaohongshu_user.py                        # 弹窗输入 URL
python xiaohongshu_user.py "https://www.xiaohongshu.com/user/profile/xxx?xsec_token=..."
python xiaohongshu_user.py "URL" 50               # 采集 50 篇
```

输出到 `05_long_project/小红书/{博主昵称}/` 目录。

### xiaohongshu_ai.py — 点点 AI 问答采集

调用小红书点点 AI 搜索，保存 AI 回答为 Obsidian callout 格式。

```bash
python xiaohongshu_ai.py                          # 弹窗输入关键词
python xiaohongshu_ai.py "婚前多久试婚纱"
```

输出到 `05_long_project/小红书/` 根目录，文件名即问题文本。

### xiaohongshu_ai_batch.py — AI 问答批量采集

读取问题清单文件，逐个调用 AI 搜索。间隔比普通采集更长（10-20 秒），因为 AI 接口更敏感。

```bash
python xiaohongshu_ai_batch.py                                    # 默认读 问题清单.md
python xiaohongshu_ai_batch.py "d:\path\to\questions.md"          # 指定清单文件
```

清单文件格式（每行一个问题，支持 `- 问题`、`1. 问题`、纯文本三种格式）：

```markdown
- 婚前多久试婚纱
- 备孕需要做哪些检查
- 新生儿黄疸怎么处理
```

默认清单路径：`d:/obsidian/demo/inbox/问题清单.md`

---

## BOSS直聘系列

### boss_search.py — 职位搜索采集

搜索 BOSS直聘职位，获取列表后逐个采集职位详情（薪资、描述、公司信息等）。

```bash
python boss_search.py                              # 弹窗输入关键词 + 城市 + 数量
python boss_search.py "外贸"                       # 默认宁波, 15 个
python boss_search.py "外贸" 上海 30               # 指定城市 + 数量
python boss_search.py "外贸" 上海 30 1-3年 本科    # 指定经验 + 学历
python boss_search.py "外贸" 上海 30 不限 不限 9   # 断点续传: 从第 9 个开始
```

输出到 `05_long_project/BOSS直聘/{关键词}_{城市}.md`，包含汇总表格和职位详情区段。

**关键配置**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `DETAIL_INTERVAL_MIN/MAX` | 8-12 秒 | 详情请求间隔 |
| `DETAIL_RETRY_MAX` | 2 | 单条重试次数 |
| `BATCH_SIZE` | 5 | 批次暂停间隔 |
| `BATCH_PAUSE_MIN/MAX` | 15-25 秒 | 批次暂停时长 |
| `DETAIL_COOLDOWN_FAILS` | 2 | 连续失败冷却阈值 |
| `DETAIL_COOLDOWN_WAIT_MIN/MAX` | 60-120 秒 | 冷却等待时长 |

**断点续传**：脚本每次获取详情后立即写入文件，中断后可用第 7 个参数从指定编号继续。

### boss_resume.py — 详情断点续传

从已有 Markdown 文件中提取未获取详情的职位，补充完整。避免重新搜索导致结果不一致。

```bash
python boss_resume.py                              # 自动扫描目录下未完成的文件
python boss_resume.py "布童科技_宁波.md"           # 指定文件
python boss_resume.py "布童科技_宁波.md" 8         # 从第 8 个开始补充
```

**增量写入**：每获取一个详情成功后立即写入文件，脚本被终止也不丢失已获取的数据。

**全失败检测**：当所有详情获取都失败时，提示 securityId 可能已过期，建议重新搜索而非续传。

### boss_fix_status.py — 修复采集状态

检查所有 BOSS直聘 Markdown 文件的采集完整性，将错误的"已采集"状态修正为"采集中"。

```bash
python boss_fix_status.py
```

验证逻辑：对比表格中的职位编号集合与详情区段（`### N.`）的编号集合，缺失则状态不正确。此脚本完全独立，不依赖 opencli 或其他采集模块。

---

## B站系列

### bilibili_following.py — 关注列表采集

采集 B站关注列表，输出为表格 Markdown 并缓存 JSON 供视频脚本使用。

```bash
python bilibili_following.py                       # 默认取前 50 个关注
python bilibili_following.py --limit 100           # 取前 100 个
```

输出文件：

- `05_long_project/B站关注/关注列表.md` — 表格格式
- `05_long_project/B站关注/following_cache.json` — 缓存数据（供视频脚本复用）

### bilibili_videos.py — 关注博主视频采集

依赖 `bilibili_following.py` 产出的 `following_cache.json`，采集每个关注博主的近期视频。

```bash
python bilibili_videos.py                          # 默认每人 3 条视频
python bilibili_videos.py --videos 5               # 每人 5 条
python bilibili_videos.py --refresh                # 先刷新关注列表缓存
```

输出文件：

- `05_long_project/B站关注/关注视频.md` — 全部视频（每博主一个 callout）
- `05_long_project/B站关注/本周视频.md` — 近 7 天视频（表格格式）
- `05_long_project/B站关注/本月视频.md` — 近 30 天视频（表格格式）

缓存不存在或过期时自动调用 `bilibili_following.py` 重新拉取。

---

## B站每周必看系列

基于 opencli 的 `bilibili weekly` 命令，采集 B站"每周必看"榜单视频。

### bilibili_weekly.py — 每周必看采集

采集指定期数的每周必看视频列表，保存为 Obsidian Markdown 表格。

```bash
python bilibili_weekly.py                  # 弹窗输入 (期数/数量)
python bilibili_weekly.py latest 50        # 最新一期, 取 50 条 (推荐)
python bilibili_weekly.py 200              # 指定第 200 期
python bilibili_weekly.py latest 10        # 最新一期, 取 10 条
```

输出到 `05_long_project/B站/每周必看/weekly_{期数}.md`，包含 frontmatter (含 year/month/week/number 等属性) 和视频表格。

**关键特性**：
- COOKIE 策略：weekly.ts 使用 `Strategy.COOKIE`，脚本调用时浏览器桥接约 8-15 秒
- 数字格式化：中文化显示 `1234567 → 123.5万`，`100000000 → 1.0亿`
- 标题带链接：标题列渲染为 `[标题](https://www.bilibili.com/video/BVxxx)` 可点击跳转
- 期数解析：从 series/list API 的 name 字段解析年/月/周/日期范围

### bilibili_weekly_batch.py — 每周必看批量采集

按年份批量采集每周必看视频，支持断点续传和失败重试。

```bash
python bilibili_weekly_batch.py 2026           # 生成 2026 年全部期数 (失败的可重试)
python bilibili_weekly_batch.py 2026 --limit 3  # 仅最新 3 期 (测试)
python bilibili_weekly_batch.py 2026 --skip-failed  # 跳过所有已处理 (含失败)
python bilibili_weekly_batch.py 2026 --force    # 强制全部重新追加 (含已成功)
```

**去重策略**（基于 `_processed.json` 日志）：

| 参数 | 行为 |
| ---- | ---- |
| 默认 | 只跳过 success，失败的可重试 |
| `--skip-failed` | 跳过所有已处理 (含失败) |
| `--force` | 不跳过任何，全部重新追加 |

**失败重试机制**：B站 API 空数据是间歇性的，失败的期数下次默认重试，避免永久丢失数据。

### bilibili_weekly_by_partition.py — 每周必看按分区归档

调用 weekly CLI 获取视频，按 tname (分区) 分类，将每期视频追加到对应分区笔记的表格中。

```bash
python bilibili_weekly_by_partition.py latest       # 最新一期 (推荐)
python bilibili_weekly_by_partition.py 200           # 指定第 200 期
python bilibili_weekly_by_partition.py 200 --force  # 强制重新追加
```

输出到 `05_long_project/B站/每周必看/分区/{分区名}.md`，每个分区一个文件，表格按期数倒序排列（最新在顶部）。

**表格结构**：

```
| 年 | 月 | 周 | 期数 | 标题 | UP主 | 时长 | 发布 | 播放 | 点赞 | 投币 |
```

**处理日志**：`分区/_processed.json` 记录每期处理状态 (success/empty/error)，避免重复处理。

---

## GitHub 系列

### github_trending.py — Trending 仓库采集

调用 `opencli github trending` 命令，获取 GitHub Trending 仓库列表。

```bash
python github_trending.py                     # 弹窗: 语言/区间/数量
python github_trending.py python              # 指定语言
python github_trending.py python weekly 10    # 语言/区间/数量
python github_trending.py "" weekly 30        # 留空=全语言
python github_trending.py python daily 25 --no-translate  # 跳过翻译
```

输出到 `05_long_project/GitHub/Trending/trending_{语言}_{区间}_{日期}.md`。

**关键特性**：
- 策略：COOKIE (需浏览器桥接，单次约 10-30 秒)
- 描述翻译：使用 `deep-translator` 包批量翻译为中文（技术术语保留）
- 表格列：rank, repo, stars, stars_today, language, description, 中文翻译

### github_topic.py — Topic 仓库采集

调用 `opencli github topic` 命令，通过 GitHub Search API 获取指定 topic 下的 Top 仓库。

```bash
python github_topic.py                            # 弹窗输入
python github_topic.py awesome                    # 默认排序
python github_topic.py react --sort updated       # 按最近更新
python github_topic.py rust --limit 10            # 限制数量
python github_topic.py machine-learning --no-translate  # 跳过翻译
```

输出到 `05_long_project/GitHub/Topic/topic_{topic}_{sort}_{日期}.md`。

**关键特性**：
- 策略：public API (无浏览器，约 2 秒)
- 排序：stars / forks / updated
- 描述翻译：同 github_trending.py
- 数字格式化：`12345 → 12.3k`，`1200000 → 1.2M`

---

## 拼多多系列

### pdd_search.py — 商品搜索（综合排序）

搜索拼多多商品，结果按综合排序，图片通过 CLI 的 `--download` 参数自动下载。

```bash
python pdd_search.py                               # 弹窗输入关键词 + 数量
python pdd_search.py "手机壳"                       # 默认采集 10 个
python pdd_search.py "手机壳" 5                     # 指定数量
```

输出到 `05_long_project/拼多多/{关键词}.md`，图片下载到 `inbox/附件/`。

### pdd_search_cheap.py — 商品搜索（价格升序）

与 `pdd_search.py` 类似，但结果按价格从低到高排序。服务端排序 + 客户端二次排序确保结果严格升序。

```bash
python pdd_search_cheap.py                         # 弹窗输入关键词 + 数量
python pdd_search_cheap.py "手机壳"                 # 默认采集 10 个
python pdd_search_cheap.py "手机壳" 5               # 指定数量
```

输出文件名带 `_低价` 后缀以区分普通搜索，frontmatter 中 `sort: price_asc`。

### pdd_search_batch.py — 批量低价搜索

读取待购清单文件，逐个调用 `pdd_search_cheap` 的搜索逻辑。

```bash
python pdd_search_batch.py                                          # 默认读 商品购买清单.md, 每个搜 3 个
python pdd_search_batch.py "d:\path\to\list.md"                     # 指定清单文件
python pdd_search_batch.py "d:\path\to\list.md" 5                   # 每个商品搜 5 个结果
```

默认清单路径：`d:/obsidian/demo/inbox/商品购买清单.md`

### pdd_search_batch_default.py — 批量综合搜索

与 `pdd_search_batch.py` 类似，但使用综合排序。**增强特性**：

- **防系统睡眠**：通过 `ctypes SetThreadExecutionState` 防止批量采集期间系统休眠
- **断点续传**：进度文件 `_pdd_batch_progress.json` + 输出目录 md 文件双重判断已完成项
- **心跳 sleep**：长睡眠期间输出心跳日志

```bash
python pdd_search_batch_default.py                                  # 默认读 商品购买清单.md, 每个搜 3 个
python pdd_search_batch_default.py "d:\path\to\list.md"             # 指定清单文件
python pdd_search_batch_default.py "d:\path\to\list.md" 5           # 每个商品搜 5 个结果
```

---

## 依赖关系

```
xiaohongshu_collect.py  ← 核心基础模块
├── xiaohongshu_note.py
├── xiaohongshu_ai.py
│   └── xiaohongshu_ai_batch.py
├── xiaohongshu_user.py
├── bilibili_following.py
│   └── bilibili_videos.py (依赖 following_cache.json)
├── bilibili_weekly.py
│   ├── bilibili_weekly_batch.py
│   └── bilibili_weekly_by_partition.py
├── github_trending.py
├── github_topic.py
├── pdd_search.py
│   └── pdd_search_batch_default.py
└── pdd_search_cheap.py
    └── pdd_search_batch.py

boss_search.py  ← 独立（仅导入 xiaohongshu_collect 的基础工具）
boss_resume.py  ← 独立（仅导入 xiaohongshu_collect 的基础工具）
boss_fix_status.py  ← 完全独立（仅用标准库 re + pathlib）
```

## 日志机制

每次运行自动创建独立日志文件，位于 `05_long_project/程序运行日志/`：

```
{脚本名}_{YYYYMMDD}_{HHMMSS}.log
```

例如 `boss_search_20260728_112322.log`。日志通过 `xiaohongshu_collect.py` 的 `log()` 函数统一输出到 console 和文件，UTF-8 编码，处理了 Windows GBK 控制台的编码问题。

## 常见问题

### securityId 以 `-` 开头导致 CLI 报错

BOSS直聘的 securityId 偶尔以 `-` 开头，会被 Commander.js 误认为命令选项。已在 `boss_search.py` 和 `boss_resume.py` 中通过 `--` 分隔符修复：

```python
args = ["boss", "detail", "-f", "json", "--", security_id]
```

### securityId 含 `--` 导致 Obsidian 表格渲染异常

securityId 中的 `--` 会破坏 HTML 注释 `<!-- -->`，导致 Obsidian 提前关闭注释。已通过 base64 编码修复，存储格式为 `<!-- sid:b64:xxxx -->`，读取时自动解码，兼容旧格式。

### 脚本在长睡眠期间被终止

长 `time.sleep()` 期间无输出，父进程可能误判卡死。已通过 `_sleep_with_heartbeat()` 修复，每 10 秒输出一次心跳日志。

### 浏览器 cookie 过期

opencli 依赖浏览器 cookie 访问平台数据。若采集全部失败，检查 Chrome 是否已登录目标平台，或运行 `opencli doctor` 诊断浏览器桥接状态。
