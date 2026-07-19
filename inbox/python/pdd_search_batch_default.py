# -*- coding: utf-8 -*-
"""拼多多批量搜索 (综合排序)

读取待购清单文件 (每行一个商品名, 支持 `- item` 或纯文本), 逐个调用
pdd_search 的搜索逻辑 (综合排序), 生成多个 Obsidian Markdown 文件。

与 pdd_search_batch.py 的区别:
  - 本脚本使用综合排序 (pdd_search), 文件名无 _低价 后缀
  - pdd_search_batch.py 使用价格升序 (pdd_search_cheap), 文件名带 _低价 后缀

用法:
    python pdd_search_batch_default.py                                    # 默认读 商品购买清单.md, 每个搜 3 个
    python pdd_search_batch_default.py "d:\\path\\to\\list.md"            # 指定清单文件
    python pdd_search_batch_default.py "d:\\path\\to\\list.md" 5          # 每个商品搜 5 个结果
"""

import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# 复用 pdd_search 的搜索/生成逻辑 (综合排序)
sys.path.insert(0, str(Path(__file__).parent))
from pdd_search import (  # noqa: E402
    IMAGES_ROOT,
    OUTPUT_ROOT,
    build_markdown,
    log,
    sanitize_filename,
    search_products,
    write_markdown,
)

# ============ 配置 ============
DEFAULT_LIST_FILE = r"d:\obsidian\demo\inbox\商品购买清单.md"
DEFAULT_LIMIT = 3  # 每个商品默认搜索 3 个结果 (批量场景不宜过多)

# 防风控: 每次搜索之间的间隔 (秒)
INTERVAL_MIN = 5
INTERVAL_MAX = 10
# 批次休息: 每搜完 N 个商品后长休息
BATCH_SIZE = 5
BATCH_REST_MIN = 20
BATCH_REST_MAX = 40

# ============ 防止系统睡眠 (Windows) ============
# 长时间运行批处理时, Windows 电源策略会在空闲数分钟后让系统进入睡眠,
# 导致 python 进程被挂起, 网络断开, opencli 子进程异常, 整个批处理静默中断。
# 使用 SetThreadExecutionState 在运行期间阻止系统睡眠。
try:
    import ctypes
    _ES_CONTINUOUS = 0x80000000
    _ES_SYSTEM_REQUIRED = 0x00000001
    _ES_DISPLAY_REQUIRED = 0x00000002
    HAS_CTYPES = True
except (ImportError, AttributeError):
    HAS_CTYPES = False


def prevent_sleep():
    """阻止系统进入睡眠 (仅 Windows 生效)"""
    if not HAS_CTYPES:
        return False
    try:
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: 保持系统运行
        # 不加 ES_DISPLAY_REQUIRED, 允许屏幕关闭省电, 但不睡眠
        ctypes.windll.kernel32.SetThreadExecutionState(
            _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED
        )
        return True
    except Exception:
        return False


def allow_sleep():
    """恢复系统默认睡眠策略"""
    if not HAS_CTYPES:
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
    except Exception:
        pass


# ============ 断点续传 (进度文件) ============
PROGRESS_FILE = OUTPUT_ROOT / "_pdd_batch_progress.json"


def load_progress():
    """加载进度文件, 返回 {keyword: {"status":..., "path":..., "count":..., "time":...}}"""
    if not PROGRESS_FILE.exists():
        return {}
    try:
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"进度文件读取失败 (忽略, 从头开始): {e}")
        return {}


def save_progress(progress):
    """保存进度文件 (原子写: 先写 .tmp 再 replace)"""
    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        tmp = PROGRESS_FILE.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(progress, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(PROGRESS_FILE)
    except Exception as e:
        log(f"进度文件保存失败 (不影响主流程): {e}")


def find_existing_md(keyword):
    """查找输出目录中该商品已生成的 md 文件 (基础名或带时间戳后缀)

    write_markdown 命名规则: {safe_name}.md, 同名已存在时加 _HHMMSS 后缀。
    返回 Path 或 None (空文件视为未完成)。
    """
    safe_name = sanitize_filename(keyword)[:60] or "untitled"
    base = OUTPUT_ROOT / f"{safe_name}.md"
    if base.exists() and base.stat().st_size > 0:
        return base
    for p in OUTPUT_ROOT.glob(f"{safe_name}_*.md"):
        if p.stat().st_size > 0:
            return p
    return None


def check_done(progress, keyword):
    """检查某商品是否已完成, 返回 (done, info)

    done=True 时 info 为 {"count":..., "path":...}:
    - 优先用进度文件记录 (含商品数量)
    - 进度文件无记录但输出目录已有 md 文件 -> 兜底返回 (count 未知记为 0)
    """
    info = progress.get(keyword)
    if info and info.get("status") == "ok":
        md_path = info.get("path")
        if md_path and Path(md_path).exists():
            return True, info
    # 兜底: 输出目录已有 md 文件 (即使进度文件丢失/损坏)
    existing = find_existing_md(keyword)
    if existing:
        return True, {"status": "ok", "count": 0, "path": str(existing), "note": "detected from existing md"}
    return False, None


# ============ 心跳 sleep ============
def sleep_with_heartbeat(seconds, label="", heartbeat_interval=10):
    """sleep 但每隔 heartbeat_interval 秒打印心跳, 避免日志长时间无输出看似卡住

    用于批次休息 (20-40s) 等较长的等待。短间隔 (5-10s) 直接 sleep 不打印心跳。
    """
    if label:
        log(f"  {label} ({seconds:.0f}s) ...")
    elapsed = 0.0
    while elapsed < seconds:
        chunk = min(heartbeat_interval, seconds - elapsed)
        time.sleep(chunk)
        elapsed += chunk
        if elapsed < seconds:
            log(f"  ... 心跳 ({elapsed:.0f}/{seconds:.0f}s)")


def parse_list_file(file_path):
    """解析清单文件, 返回商品名列表

    支持:
      - `- 商品名` (Markdown 列表)
      - `1. 商品名` (有序列表)
      - `商品名` (纯文本)
    跳过空行和注释 (以 # 开头)
    """
    p = Path(file_path)
    if not p.exists():
        log(f"清单文件不存在: {file_path}")
        return []

    items = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 去除前缀: `- `, `* `, `1. `, `- [ ] ` 等
        cleaned = re.sub(r'^[-*]\s*(?:\[[ xX]\]\s*)?', '', line)
        cleaned = re.sub(r'^\d+\.\s*', '', cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            items.append(cleaned)
    return items


def show_batch_dialog():
    """tkinter 弹窗: 清单文件路径 + 每个商品数量"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        return None, DEFAULT_LIMIT

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = simpledialog.askstring(
        "拼多多批量搜索 (综合排序)",
        "请输入清单文件路径:",
        initialvalue=DEFAULT_LIST_FILE,
        parent=root,
    )
    if not file_path or not file_path.strip():
        root.destroy()
        return None, 0
    file_path = file_path.strip()

    limit_str = simpledialog.askstring(
        "每个商品数量",
        "每个商品搜索几个结果? (1-20)",
        initialvalue=str(DEFAULT_LIMIT),
        parent=root,
    )
    try:
        limit = max(1, min(20, int(limit_str)))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    root.destroy()
    return file_path, limit


def main():
    log("=" * 60)
    log("拼多多批量搜索 (综合排序) 启动")
    log("=" * 60)

    # 0. 阻止系统睡眠 (防止空闲后 Windows 睡眠导致中断)
    if prevent_sleep():
        log("已阻止系统睡眠 (运行期间不会自动休眠, 结束后自动恢复)")
    else:
        log("警告: 无法阻止系统睡眠 (非 Windows 或无 ctypes), 请保持电脑唤醒")

    try:
        return _run_batch()
    finally:
        # 无论正常结束 / 异常 / Ctrl+C, 都恢复系统睡眠策略
        allow_sleep()
        log("已恢复系统睡眠策略")


def _run_batch():
    # 1. 获取清单文件路径 + 每个商品数量
    list_file = DEFAULT_LIST_FILE
    limit = DEFAULT_LIMIT
    if len(sys.argv) >= 2:
        list_file = sys.argv[1].strip()
        if len(sys.argv) >= 3:
            try:
                limit = max(1, min(20, int(sys.argv[2])))
            except ValueError:
                limit = DEFAULT_LIMIT
    else:
        list_file, limit = show_batch_dialog()

    if not list_file:
        log("未指定清单文件, 退出")
        return 1

    # 2. 解析清单
    items = parse_list_file(list_file)
    if not items:
        log(f"清单为空或无法解析: {list_file}")
        return 1

    # 3. 加载进度 (断点续传)
    progress = load_progress()
    skipped = 0

    log(f"清单文件: {list_file}")
    log(f"共 {len(items)} 个商品, 每个搜索 {limit} 个结果")
    log(f"输出目录: {OUTPUT_ROOT}")
    log(f"进度文件: {PROGRESS_FILE}")
    # 断点续传检测: 进度文件 + 输出目录 md 文件双重判断
    done_count = sum(1 for kw in items if check_done(progress, kw)[0])
    if done_count:
        log(f"断点续传: 检测到 {done_count} 个已完成, 将跳过")
    log("-" * 60)

    # 4. 逐个搜索
    results = []
    total = len(items)
    start_time = time.time()

    for i, keyword in enumerate(items, 1):
        # 断点续传: 跳过已完成 (进度文件 + md 文件兜底)
        done, info = check_done(progress, keyword)
        if done:
            count_str = info.get("count", "?")
            note = info.get("note", "")
            tag = f" ({note})" if note else ""
            log(f"[{i}/{total}] {keyword} - 已完成, 跳过 ({count_str} 个商品){tag}")
            results.append({
                "status": "ok",
                "keyword": keyword,
                "count": info.get("count", 0),
                "path": info.get("path", ""),
                "skipped": True,
            })
            skipped += 1
            # 若仅靠 md 兜底判定 (进度文件无记录), 补登进度文件
            if "note" in info:
                progress[keyword] = {
                    "status": "ok",
                    "count": info.get("count", 0),
                    "path": info.get("path", ""),
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "note": "detected from existing md",
                }
                save_progress(progress)
            continue

        log(f"[{i}/{total}] {keyword}")

        # 间隔 (第 2 条起): 短间隔直接 sleep, 无心跳
        if i > 1:
            wait = random.uniform(INTERVAL_MIN, INTERVAL_MAX)
            time.sleep(wait)

        # 批次休息: 较长等待, 用心跳 sleep
        if i > 1 and (i - 1) % BATCH_SIZE == 0:
            rest = random.uniform(BATCH_REST_MIN, BATCH_REST_MAX)
            sleep_with_heartbeat(rest, label=f"已处理 {i-1}/{total}, 批次休息")

        # 准备图片目录
        images_dir_name = f"pdd_{sanitize_filename(keyword)[:30]}"
        images_dir = IMAGES_ROOT / images_dir_name
        images_dir.mkdir(parents=True, exist_ok=True)

        # 搜索 + 生成 markdown
        try:
            products = search_products(keyword, limit, images_dir)
            if not products:
                log(f"  失败: 未获取到商品")
                results.append({"status": "fail", "keyword": keyword, "error": "无商品"})
                continue

            md_content = build_markdown(keyword, products, images_dir)
            md_path = write_markdown(keyword, md_content)
            log(f"  OK -> {md_path.name} ({len(products)} 个商品)")
            results.append({
                "status": "ok",
                "keyword": keyword,
                "count": len(products),
                "path": str(md_path),
            })
            # 成功后立即保存进度 (断点续传关键)
            progress[keyword] = {
                "status": "ok",
                "count": len(products),
                "path": str(md_path),
                "time": datetime.now().isoformat(timespec="seconds"),
            }
            save_progress(progress)
        except Exception as e:
            log(f"  异常: {e}")
            results.append({"status": "fail", "keyword": keyword, "error": str(e)})

    # 5. 汇总
    elapsed = time.time() - start_time
    ok_count = sum(1 for r in results if r["status"] == "ok")
    fail_count = len(results) - ok_count

    log("=" * 60)
    log(f"批量搜索完成: 成功 {ok_count}/{total}, 失败 {fail_count}, 跳过 {skipped}, 用时 {elapsed:.0f}s")

    if fail_count:
        log("失败列表:")
        for r in results:
            if r["status"] != "ok":
                log(f"  - {r['keyword']}: {r.get('error', '?')}")

    return 0 if fail_count == 0 else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
