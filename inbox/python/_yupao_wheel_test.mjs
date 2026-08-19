// 实验: CDP 滚轮被检测的维度 — mousemove 前置 / deltaY 大小 / 坐标
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

async function cdp(method, params) {
    return sendCommand('cdp', { cdpMethod: method, cdpParams: params, workspace: 'default', tabId: page._tabId });
}

async function state(label) {
    const st = await page.evaluate(`location.href.slice(0,50) + ' | cards=' + document.querySelectorAll('div[data-index]').length + ' | mainTop=' + Math.round((document.querySelector('#mainR')||{scrollTop:-1}).scrollTop) + ' | bodyY=' + Math.round(scrollY)`).catch(e => 'eval-fail: ' + String(e.message).slice(0, 60));
    console.log(`${label}: ${st}`);
    return st;
}

await state('基线');

// 实验 A: 前置 mouseMoved + 单格 120px 滚轮 (模拟真实用户)
console.log('\n== 实验A: mouseMoved + wheel(120) ==');
try {
    await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 825, y: 470 });
    await sleep(150);
    await cdp('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 825, y: 470, deltaX: 0, deltaY: 120 });
    await sleep(2500);
    await state('A后');
} catch (e) {
    console.log(`A 异常: ${String(e.message).slice(0, 100)}`);
    await state('A失败后');
}

// 页面若还活着, 继续实验 B: 连续 3 个单格滚轮
if (!(await state('存活检查')).startsWith('eval-fail') && !(await page.evaluate(`location.href`).catch(() => '')).includes('about:blank')) {
    console.log('\n== 实验B: 连续3x wheel(120) ==');
    try {
        for (let i = 0; i < 3; i++) {
            await cdp('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 825, y: 470, deltaX: 0, deltaY: 120 });
            await sleep(120);
        }
        await sleep(2500);
        await state('B后');
    } catch (e) {
        console.log(`B 异常: ${String(e.message).slice(0, 100)}`);
    }
}

const finalUrl = await page.evaluate(`location.href`).catch(() => 'eval-fail');
console.log(`\n最终 URL: ${finalUrl.slice(0, 60)}`);
console.log(finalUrl.includes('about:blank') ? '页面被杀' : '页面存活');
process.exit(0);
