// 提取无限列表组件状态: requestParams / pageInfo / hasMore / ref 函数源码
import { Page } from 'file:///D:/voice/opencli-main/dist/browser/index.js';
import { writeFileSync } from 'node:fs';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const page = new Page('default');

const url = 'https://www.yupao.com/topic/a388c0/?keywords=' + encodeURIComponent('文员');
await page.goto(url, { waitUntil: 'none' });
for (let i = 0; i < 25; i++) {
    await sleep(2000);
    try {
        if (await page.evaluate(`document.querySelectorAll('div[data-index]').length > 0`)) break;
    } catch { }
}
console.log('页面就绪');

const info = await page.evaluate(`(() => {
  const sentinel = document.querySelector('.yp-pagelist-infinite');
  const fiberKey = Object.keys(sentinel).find(k => k.startsWith('__reactFiber$'));
  let f = sentinel[fiberKey];
  for (let i = 0; i < 8 && f; i++) f = f.return;
  // hooks 链
  let ms = f.memoizedState;
  const hooks = [];
  let i = 0;
  while (ms && i < 20) { hooks.push(ms.memoizedState); ms = ms.next; i++; }
  // hook2 = 状态对象 {list, requestParams, hasMore, showEmptyCard, pageInfo}
  const st = hooks[2];
  const out = { state: {} };
  if (st && typeof st === 'object') {
    out.state.listLen = Array.isArray(st.list) ? st.list.length : typeof st.list;
    out.state.hasMore = st.hasMore;
    out.state.showEmptyCard = st.showEmptyCard;
    try { out.state.pageInfo = JSON.parse(JSON.stringify(st.pageInfo)); } catch { out.state.pageInfo = String(st.pageInfo).slice(0, 100); }
    try { out.state.requestParams = JSON.parse(JSON.stringify(st.requestParams)); } catch { out.state.requestParams = String(st.requestParams).slice(0, 200); }
  }
  // hook4 = ref 对象, hook5 = ref 函数 (可能是 loadMore)
  const refObj = hooks[4];
  if (refObj && refObj.current && typeof refObj.current === 'object') {
    out.refObjKeys = Object.keys(refObj.current).slice(0, 20);
  }
  const refFn = hooks[5];
  if (refFn && refFn.current) {
    out.loadMoreFnSrc = String(refFn.current).slice(0, 2500);
  }
  return out;
})()`).catch(e => ({ err: String(e.message).slice(0, 100) }));

console.log(JSON.stringify(info, null, 1).slice(0, 4500));
writeFileSync('d:/obsidian/demo/inbox/python/_yupao_state.json', JSON.stringify(info, null, 1), 'utf-8');
process.exit(0);
