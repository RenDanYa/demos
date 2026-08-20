// 提取 __NEXT_DATA__ 的分页字段 + prefetchInfo (可能包含下一页 API)
import { Page } from 'file:///D:/voice/opencli-main/dist/browser/index.js';
import { writeFileSync } from 'node:fs';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const page = new Page('default');

const url = 'https://www.yupao.com/topic/a388c0/?keywords=' + encodeURIComponent('文员');
await page.goto(url, { waitUntil: 'none' });
let cards = 0;
for (let i = 0; i < 20; i++) {
    await sleep(2000);
    try {
        cards = await page.evaluate(`document.querySelectorAll('div[data-index]').length`);
        if (cards > 0) break;
    } catch { }
}
console.log(`cards=${cards}`);

const data = await page.evaluate(`(() => {
  const nd = document.getElementById('__NEXT_DATA__');
  if (!nd) return { err: 'no-next-data' };
  const j = JSON.parse(nd.textContent);
  const pp = j.props?.pageProps || {};
  const out = {
    page: pp.page,
    pageSize: pp.pageSize,
    isLoadFinished: pp.isLoadFinished,
    listJobLen: Array.isArray(pp.listJob) ? pp.listJob.length : typeof pp.listJob,
    prefetchInfo: pp.prefetchInfo,
    ssrInfo: pp._ssrInfo ? JSON.stringify(pp._ssrInfo).slice(0, 600) : undefined,
    listJob0: Array.isArray(pp.listJob) && pp.listJob[0] ? Object.keys(pp.listJob[0]).slice(0, 30) : undefined,
    buildId: j.buildId,
    page_path: j.page
  };
  return out;
})()`);

console.log(JSON.stringify(data, null, 2).slice(0, 2500));
writeFileSync('d:/obsidian/demo/inbox/python/_yupao_nextdata.json', JSON.stringify(data, null, 2), 'utf-8');
console.log('已保存 _yupao_nextdata.json');
process.exit(0);
