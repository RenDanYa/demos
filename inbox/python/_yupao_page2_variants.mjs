// 测试分页参数变体: urlPage=2 / topic /p2/ 路径 / DOM 分页链接
import { Page } from 'file:///D:/voice/opencli-main/dist/browser/index.js';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const page = new Page('default');

const base = 'https://www.yupao.com/topic/a388c0/?keywords=' + encodeURIComponent('文员');

async function gotoAndWait(targetUrl) {
    await page.goto(targetUrl, { waitUntil: 'none' });
    for (let i = 0; i < 25; i++) {
        await sleep(2000);
        try {
            const ok = await page.evaluate(`!!document.getElementById('__NEXT_DATA__') || document.querySelectorAll('div[data-index]').length > 0`);
            if (ok) return true;
        } catch { }
    }
    return false;
}

async function firstJob(label) {
    const r = await page.evaluate(`(() => {
    const nd = document.getElementById('__NEXT_DATA__');
    let page1 = '', firstId = '', n = 0;
    if (nd) {
      try {
        const j = JSON.parse(nd.textContent);
        const pp = j.props?.pageProps || {};
        page1 = String(pp.page);
        const lj = pp.listJob || [];
        n = lj.length;
        firstId = lj[0] ? String(lj[0].id || '') : '';
      } catch {}
    }
    return { page: page1, n, firstId };
  })()`).catch(e => ({ err: String(e.message).slice(0, 60) }));
    console.log(`[${label}] ${JSON.stringify(r)}`);
    return r;
}

// 基线 page1
if (!(await gotoAndWait(base))) { console.log('基线加载失败'); process.exit(1); }
const p1 = await firstJob('page1-基线');

// DOM 分页链接
const links = await page.evaluate(`(() => {
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll('a[href]')) {
    const h = a.getAttribute('href') || '';
    if (/\/p\d+\/|[?&](url)?[Pp]age=\d+|下一页|pageNo/.test(h) && !seen.has(h)) { seen.add(h); out.push(h.slice(0, 100)); }
    if (out.length >= 10) break;
  }
  return out;
})()`).catch(() => []);
console.log(`DOM 分页链接: ${JSON.stringify(links)}`);

// 变体 A: topic /p2/ 路径
if (await gotoAndWait('https://www.yupao.com/topic/a388c0/p2/?keywords=' + encodeURIComponent('文员'))) {
    await firstJob('topic-p2路径');
} else { console.log('[topic-p2路径] 加载失败'); }

// 变体 B: _next/data + urlPage=2
const buildId = '9JWr33IjbGog0CiQHKmml';
const dUrl = `https://www.yupao.com/_next/data/${buildId}/job/recommend.json?keywords=${encodeURIComponent('文员')}&urlAreaId=388&urlFlag=%2F&urlOccIdStr=c0&urlPageType=topic&urlPage=2`;
if (await gotoAndWait(dUrl)) {
    const r = await page.evaluate(`(() => {
    try {
      const j = JSON.parse(document.body.innerText);
      const pp = j.pageProps || {};
      const lj = pp.listJob || [];
      return { page: pp.page, n: lj.length, firstId: lj[0] ? String(lj[0].id || '') : '' };
    } catch (e) { return { err: String(e.message).slice(0, 60) }; }
  })()`).catch(() => ({ err: 'eval-fail' }));
    console.log(`[urlPage=2] ${JSON.stringify(r)}`);
} else { console.log('[urlPage=2] 加载失败'); }
process.exit(0);
