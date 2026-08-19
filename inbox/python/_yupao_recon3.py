# -*- coding: utf-8 -*-
"""验证假设: 有头真实Chrome + CDP可信滚轮事件 能否绕过鱼泡机器人检测并触发分页加载"""
import json
import time
from playwright.sync_api import sync_playwright

URL = "https://www.yupao.com/topic/a388c0/?keywords=%E6%96%87%E5%91%98"
PROFILE = r"d:\obsidian\demo\inbox\python\.chrome-recon-profile"

api_requests = []

def on_request(req):
    try:
        if req.resource_type in ("xhr", "fetch") and "search" in req.url:
            entry = {"t": round(time.time(), 1), "method": req.method, "url": req.url[:150]}
            try:
                entry["body"] = req.post_data[:800] if req.post_data else None
            except Exception:
                entry["body"] = None
            try:
                h = dict(req.headers)
                entry["hdr_keys"] = sorted(h.keys())
                entry["interesting"] = {k: h.get(k, "") for k in
                                        ("token", "deviceid", "sign", "signature", "nonce", "timestamp",
                                         "user-agent", "content-type") if h.get(k)}
            except Exception:
                pass
            api_requests.append(entry)
    except Exception:
        pass

def on_response(resp):
    try:
        if "job/search" in resp.url:
            body = resp.text()[:300]
            print(f"[resp {resp.status}] {resp.url[:100]}")
            print(f"    body[:300]: {body}")
    except Exception:
        pass

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="chrome",
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--window-position=2000,2000"],
    )
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    page = ctx.new_page()
    page.on("request", on_request)
    page.on("response", on_response)

    print("== goto ==")
    page.goto(URL, wait_until="domcontentloaded", timeout=90000)
    for i in range(45):
        page.wait_for_timeout(2000)
        n = page.evaluate("document.querySelectorAll('div[data-index]').length")
        print(f"[{i*2}s] url={page.url[:60]} cards={n}")
        if n > 0:
            break

    page.wait_for_timeout(3000)

    # CDP 可信滚轮事件 x12 — 观察卡片数是否增长、页面是否被杀
    print("== trusted wheel scroll x12 ==")
    for i in range(12):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(2200)
        n = page.evaluate("document.querySelectorAll('div[data-index]').length")
        print(f"[wheel {i+1}] cards={n} url={page.url[:50]}")

    # 提取当前 DOM 职位数(去重)
    uniq = page.evaluate("""(() => {
        const ids = new Set();
        document.querySelectorAll('a[href*="/zhaogong/"]').forEach(a => {
            const m = (a.getAttribute('href') || '').match(/\\/zhaogong\\/(\\d+)\\//);
            if (m) ids.add(m[1]);
        });
        return ids.size;
    })()""")
    print(f"[unique job ids in DOM] {uniq}")

    print("== captured search API requests ==")
    for r in api_requests:
        print(json.dumps(r, ensure_ascii=False, indent=1))

    browser.close()
