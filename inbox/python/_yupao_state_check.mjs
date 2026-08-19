// 检查 wheel 失败后页面状态: tab 是否存活/跳转/崩溃
import { Page } from 'file:///D:/voice/opencli-main/dist/browser/index.js';
import { sendCommand } from 'file:///D:/voice/opencli-main/dist/browser/daemon-client.js';

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
console.log(`初始 cards=${cards} tabId=${page._tabId}`);

// 单发一次 wheel, 观察前后状态
const before = await page.evaluate(`location.href + ' | ' + document.title`).catch(e => 'eval-fail: ' + e.message);
console.log(`wheel 前: ${before}`);

try {
    const r = await sendCommand('cdp', {
        cdpMethod: 'Input.dispatchMouseEvent',
        cdpParams: { type: 'mouseWheel', x: 825, y: 470, deltaX: 0, deltaY: 500 },
        workspace: 'default',
        tabId: page._tabId,
    });
    console.log(`wheel 返回: ${JSON.stringify(r).slice(0, 150)}`);
} catch (e) {
    console.log(`wheel 异常: ${String(e.message).slice(0, 150)}`);
}

await sleep(3000);

// wheel 后页面状态
const after = await page.evaluate(`location.href + ' | ' + document.title + ' | cards=' + document.querySelectorAll('div[data-index]').length`).catch(e => 'eval-fail: ' + e.message);
console.log(`wheel 后: ${after}`);

// 再试一次 exec (普通 evaluate 是否还活着)
const t2 = await page.evaluate(`'exec-alive ' + Date.now()`).catch(e => 'exec-fail: ' + e.message);
console.log(`exec 检查: ${t2}`);

// 列出所有 tab
const tabs = await sendCommand('tabs', { op: 'list', workspace: 'default' }).catch(e => ({ err: String(e.message).slice(0, 100) }));
console.log(`tabs: ${JSON.stringify(tabs).slice(0, 500)}`);
process.exit(0);
