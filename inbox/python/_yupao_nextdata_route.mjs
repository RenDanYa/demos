// 干净测试: 数据路由 page 参数变体 (page=2 / urlPage=2 / pageNo=2)
// 带 tabId 失配自动恢复 (被杀后重建 tab)
import { Page } from 'file:///D:/voice/opencli-main/dist/browser/index.js';
import { sendCommand } from 'file:///D:/voice/opencli-main/dist/browser/daemon-client.js';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const page = new Page('default');
const buildId = '9JWr33IjbGog0CiQHKmml';
const kw = encodeURIComponent('文员');
const q = `keywords=${kw}&urlAreaId=388&urlFlag=%2F&urlOccIdStr=c0&urlPageType=topic`;

async function syncTabId() {
    try {
        const tabs = await sendCommand('tabs', { op: 'list', workspace: 'default' });
        if (Array.isArray(tabs) && tabs.length > 0) page._tabId = tabs[0].tabId;
    } catch { }
}

async function tryDataUrl(extraParam, label) {
    const dataUrl = `https://www.yupao.com/_next/data/${buildId}/job/recommend.json?${q}&${extraParam}`;
    await page.goto(dataUrl, { waitUntil: 'none' });
    await sleep(5000);
    await syncTabId();
    const r = await page.evaluate(`(() => {
    try {
      const j = JSON.parse(document.body.innerText);
      const pp = j.pageProps || {};
      const lj = pp.listJob || [];
      return { ok: true, page: pp.page, n: lj.length, firstId: lj[0] ? String(lj[0].id) : '' };
    } catch (e) { return { ok: false, url: location.href.slice(0, 50), textLen: document.body ? document.body.innerText.length : -1 }; }
  })()`).catch(async (e) => {
        await syncTabId();
        return { ok: false, err: String(e.message).slice(0, 60) };
    });
    console.log(`[${label}] ${JSON.stringify(r)}`);
    return r;
}

// 基线: page=1 无参数 (上一轮验证可返回 JSON)
await tryDataUrl('', '基线无分页参数');
await sleep(2000);
await tryDataUrl('page=2', 'page=2');
await sleep(2000);
await tryDataUrl('urlPage=2', 'urlPage=2');
await sleep(2000);
await tryDataUrl('pageNo=2', 'pageNo=2');
process.exit(0);
