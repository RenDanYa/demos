import { sendCommand } from 'file:///D:/voice/opencli-main/dist/browser/daemon-client.js';

const code = `(() => {
  const t = document.body ? (document.body.innerText || '') : '';
  return JSON.stringify({
    url: location.href.slice(0, 120),
    title: document.title.slice(0, 50),
    textLen: t.length,
    head: t.slice(0, 200),
    bodyChildren: document.body ? document.body.children.length : -1,
    pre: document.body && document.body.querySelector('pre') ? document.body.querySelector('pre').textContent.slice(0, 100) : null
  });
})()`;

const r = await sendCommand('exec', { code, tabId: 138145606, workspace: 'default' });
console.log(JSON.stringify(r).slice(0, 700));
process.exit(0);
