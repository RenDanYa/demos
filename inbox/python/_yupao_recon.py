# -*- coding: utf-8 -*-
"""一次性侦察脚本: 用 Playwright 观察鱼泡搜索页的加载更多 API 与反爬行为"""
import json
import time
from playwright.sync_api import sync_playwright

URL = "https://www.yupao.com/topic/a388c0/?keywords=%E6%96%87%E5%91%98"

requests_log = []

def on_request(req):
    rtype = req.resource_type
    if rtype in ("xhr", "fetch"):
        requests_log.append({"t": round(time.time(), 1), "type": rtype, "method": req.method, "url": req.url[:220]})

def on_response(resp):
    if resp.request.resource_type in ("xhr", "fetch"):
        try:
            ct = resp.headers.get("content-type", "")
            if "json" in ct:
                body = resp.text()[:400]
                print(f"[resp {resp.status}] {resp.url[:160]}")
                print(f"    body: {body}")
        except Exception:
            pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.on("request", on_request)
    page.on("response", on_response)

    print("== goto ==")
    page.goto(URL, wait_until="domcontentloaded", timeout=90000)
    # WAF 验证 + 渲染
    for i in range(40):
        page.wait_for_timeout(2000)
        n = page.evaluate("document.querySelectorAll('div[data-index]').length")
        print(f"[{i*2}s] url={page.url[:80]} cards={n}")
        if n > 0:
            break

    # 原型补丁检查
    patched = page.evaluate("""(() => {
        const out = {};
        const names = ['scrollBy', 'scrollTo', 'scroll', 'scrollIntoView'];
        for (const n of names) {
            try { out['El_' + n] = (Element.prototype[n] || '').toString().includes('[native code]') ? 'native' : 'PATCHED: ' + Element.prototype[n].toString().slice(0, 80); } catch (e) { out['El_' + n] = 'err'; }
            try { out['Win_' + n] = (window[n] || '').toString().includes('[native code]') ? 'native' : 'PATCHED: ' + window[n].toString().slice(0, 80); } catch (e) { out['Win_' + n] = 'err'; }
        }
        return out;
    })()""")
    print("== prototype check ==")
    print(json.dumps(patched, ensure_ascii=False, indent=1))

    # __NEXT_DATA__ 检查 (首屏数据来源)
    nd = page.evaluate("""(() => {
        const el = document.getElementById('__NEXT_DATA__');
        if (!el) return '(no __NEXT_DATA__)';
        try {
            const d = JSON.parse(el.textContent);
            const keys = Object.keys(d.props?.pageProps || {});
            return 'pageProps keys: ' + keys.join(',');
        } catch (e) { return 'parse err'; }
    })()""")
    print("== next data ==")
    print(nd)

    # 真实滚轮滚动 (CDP 可信事件)
    print("== wheel scroll x5 ==")
    for i in range(5):
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(3000)
        state = page.evaluate("location.href.slice(0, 60) + ' | cards=' + document.querySelectorAll('div[data-index]').length")
        print(f"[wheel {i+1}] {state}")

    print("== all xhr/fetch requests ==")
    for r in requests_log:
        print(json.dumps(r, ensure_ascii=False))
    browser.close()
