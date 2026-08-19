// 中立页面对照: CDP 派发的滚轮事件到底有哪些可检测特征
import { Page } from 'file:///D:/voice/opencli-main/dist/browser/index.js';
import { sendCommand } from 'file:///D:/voice/opencli-main/dist/browser/daemon-client.js';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const page = new Page('default');

await page.goto('https://example.com', { waitUntil: 'none' });
await sleep(3000);

// 注入只读监听器, 记录 wheel 事件全部可观测属性
await page.evaluate(`(() => {
  window.__evts = [];
  addEventListener('wheel', (e) => {
    window.__evts.push({
      isTrusted: e.isTrusted,
      type: e.type,
      sourceCapabilities: e.sourceCapabilities === null ? 'null' : (e.sourceCapabilities ? 'obj' : 'undefined'),
      deltaMode: e.deltaMode,
      deltaY: e.deltaY,
      deltaX: e.deltaX,
      wheelDelta: typeof e.wheelDelta === 'number' ? e.wheelDelta : String(e.wheelDelta),
      clientX: e.clientX,
      clientY: e.clientY,
      screenX: e.screenX,
      screenY: e.screenY,
      timeStamp: Math.round(e.timeStamp),
      defaultPrevented: e.defaultPrevented,
      composed: e.composed,
      bubbles: e.bubbles,
      view: e.view === window ? 'window' : String(e.view)
    });
  }, { passive: true, capture: true });
  return 'listener-ready';
})()`).then(r => console.log(`监听器: ${r}`)).catch(e => console.log(`监听器失败: ${e.message}`));

// CDP: mouseMoved + mouseWheel
try {
    await sendCommand('cdp', { cdpMethod: 'Input.dispatchMouseEvent', cdpParams: { type: 'mouseMoved', x: 300, y: 200 }, workspace: 'default', tabId: page._tabId });
    await sleep(100);
    await sendCommand('cdp', { cdpMethod: 'Input.dispatchMouseEvent', cdpParams: { type: 'mouseWheel', x: 300, y: 200, deltaX: 0, deltaY: 120 }, workspace: 'default', tabId: page._tabId });
    await sleep(800);
} catch (e) {
    console.log(`CDP 异常: ${String(e.message).slice(0, 100)}`);
}

const evts = await page.evaluate(`JSON.stringify(window.__evts)`).catch(e => 'read-fail: ' + e.message);
console.log(`CDP wheel 事件属性: ${evts}`);

// 再试一次大 deltaY
await sendCommand('cdp', { cdpMethod: 'Input.dispatchMouseEvent', cdpParams: { type: 'mouseWheel', x: 300, y: 200, deltaX: 0, deltaY: 500 }, workspace: 'default', tabId: page._tabId }).catch(() => { });
await sleep(800);
const evts2 = await page.evaluate(`JSON.stringify(window.__evts)`).catch(() => '[]');
const arr = JSON.parse(evts2);
console.log(`共 ${arr.length} 个事件; deltaY=500 那个: ${JSON.stringify(arr[arr.length - 1] || {})}`);
process.exit(0);
