# -*- coding: utf-8 -*-
"""增强侦察: 捕获鱼泡搜索页真实分页请求(headers+body) + 测试 webpack 模块调用是否触发反爬"""
import json
import time
from playwright.sync_api import sync_playwright

URL = "https://www.yupao.com/topic/a388c0/?keywords=%E6%96%87%E5%91%98"

api_requests = []  # /job/v2/search 相关请求

def on_request(req):
    try:
        if req.resource_type in ("xhr", "fetch"):
            u = req.url
            if "search" in u or "job" in u:
                entry = {
                    "t": round(time.time(), 1),
                    "method": req.method,
                    "url": u[:200],
                }
                try:
                    entry["headers"] = dict(req.headers)
                except Exception:
                    pass
                try:
                    entry["body"] = req.post_data[:1500] if req.post_data else None
                except Exception:
                    entry["body"] = None
                api_requests.append(entry)
    except Exception:
        pass

def on_response(resp):
    try:
        if "search" in resp.url and resp.request.resource_type in ("xhr", "fetch"):
            ct = resp.headers.get("content-type", "")
            if "json" in ct:
                body = resp.text()[:600]
                print(f"[resp {resp.status}] {resp.url[:120]}")
                print(f"    body[:600]: {body}")
    except Exception:
        pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.on("request", on_request)
    page.on("response", on_response)

    print("== goto ==")
    page.goto(URL, wait_until="domcontentloaded", timeout=90000)
    for i in range(40):
        page.wait_for_timeout(2000)
        n = page.evaluate("document.querySelectorAll('div[data-index]').length")
        print(f"[{i*2}s] url={page.url[:80]} cards={n}")
        if n > 0:
            break

    page.wait_for_timeout(3000)

    # 1) 真实滚轮滚动 (CDP 可信事件) — 观察是否触发分页请求、是否被反爬
    print("== wheel scroll x6 ==")
    for i in range(6):
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(2500)
        state = page.evaluate("location.href.slice(0, 60) + ' | cards=' + document.querySelectorAll('div[data-index]').length")
        print(f"[wheel {i+1}] {state}")

    print("== captured API requests ==")
    for r in api_requests:
        print(json.dumps(r, ensure_ascii=False, indent=1))

    # 2) 从页面内读取 localStorage 中的 deviceId 等指纹字段
    print("== fingerprint fields ==")
    fp = page.evaluate("""(() => {
        const out = {ls: {}, ss: {}, cookieKeys: document.cookie.split(';').map(c => c.trim().split('=')[0])};
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            out.ls[k] = (localStorage.getItem(k) || '').slice(0, 100);
        }
        try {
            for (let i = 0; i < sessionStorage.length; i++) {
                const k = sessionStorage.key(i);
                out.ss[k] = (sessionStorage.getItem(k) || '').slice(0, 100);
            }
        } catch (e) {}
        return out;
    })()""")
    print(json.dumps(fp, ensure_ascii=False, indent=1))

    # 3) 测试 webpack 模块 API 调用 (与 search.js 相同逻辑)
    print("== webpack module API test ==")
    if page.url.startswith("about"):
        print("页面已被导航到 about:blank, 跳过模块测试")
    else:
        res = page.evaluate("""(async () => {
            try {
                const j = JSON.parse(document.getElementById('__NEXT_DATA__').textContent);
                const pp = j.props.pageProps || {};
                window.__ypWpReq = null;
                window.webpackChunk_N_E.push([[Math.floor(Math.random()*1e9)], {}, (r) => { window.__ypWpReq = r; }]);
                const wpReq = window.__ypWpReq;
                if (!wpReq) return {ok: false, err: 'no wpRequire'};
                const m = wpReq(11240);
                const api = m && m.Z && m.Z.java ? m.Z.java['POST/job/v2/search/job/search'] : null;
                if (!api) return {ok: false, err: 'no api fn'};
                const tok = pp.token || '';
                const body = {keywords: '文员', pageSize: 15, currentPage: 2, areaIds: [String(pp.selAreaId || '388')], occV2: [], filterCondition: {}, token: tok};
                const r = await api(body, {headers: {token: tok, deviceId: null}});
                return {ok: true, code: r && r.code, total: r && r.data && r.data.total, n: r && r.data && r.data.list ? r.data.list.length : -1};
            } catch (e) { return {ok: false, err: String(e).slice(0, 300)}; }
        })()""")
        print(json.dumps(res, ensure_ascii=False))
        page.wait_for_timeout(3000)
        state = page.evaluate("location.href.slice(0, 60) + ' | cards=' + document.querySelectorAll('div[data-index]').length")
        print(f"[after api call] {state}")

    browser.close()
