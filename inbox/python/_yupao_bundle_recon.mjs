// 侦察: 收集鱼泡页面脚本 URL + 关键线索 (wasm 检测器/分页组件/about:blank 杀手)
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

const info = await page.evaluate(`(() => {
  const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => s.getAttribute('src'));
  const inlineHits = [];
  for (const s of document.querySelectorAll('script:not([src])')) {
    const t = s.textContent || '';
    if (/about:blank|robot_inspect|pagelist|infinite|wheel/i.test(t)) {
      inlineHits.push(t.slice(0, 200));
    }
  }
  // 分页哨兵 DOM 结构
  const sentinel = document.querySelector('.yp-pagelist-infinite');
  const sentinelHtml = sentinel ? sentinel.outerHTML.slice(0, 300) : 'not-found';
  // __NEXT_DATA__ 里的分页信息
  let nextData = '';
  const nd = document.getElementById('__NEXT_DATA__');
  if (nd) {
    try {
      const j = JSON.parse(nd.textContent);
      const propsStr = JSON.stringify(j.props || {});
      nextData = 'total-len=' + propsStr.length + ' keys=' + Object.keys(j.props?.pageProps || {}).join(',');
    } catch (e) { nextData = 'parse-fail'; }
  }
  return { scripts: scripts.length, scriptList: scripts, inlineHits, sentinelHtml, nextData };
})()`);

console.log(`脚本数: ${info.scripts}`);
console.log(`哨兵 DOM: ${info.sentinelHtml}`);
console.log(`NEXT_DATA: ${info.nextData}`);
console.log(`内联命中: ${JSON.stringify(info.inlineHits).slice(0, 400)}`);
writeFileSync('d:/obsidian/demo/inbox/python/_yupao_scripts.json', JSON.stringify(info.scriptList, null, 2), 'utf-8');
console.log('脚本列表已保存到 _yupao_scripts.json');
process.exit(0);
