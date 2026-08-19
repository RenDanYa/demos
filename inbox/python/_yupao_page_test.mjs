// 快速验证: 鱼泡 topic 列表页是否支持 URL 分页 (?page=2)
// 注意: page.evaluate 的代码字符串会被反转义一次, 正则里需写 \\d 而不是 \d
import { Page } from 'file:///D:/voice/opencli-main/dist/browser/index.js';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function firstJobs(page, url, label) {
    await page.goto(url, { waitUntil: 'none' });
    let cards = 0;
    let state = '';
    for (let i = 0; i < 20; i++) {
        await sleep(2000);
        try {
            cards = await page.evaluate(`document.querySelectorAll('div[data-index]').length`);
            if (cards > 0) break;
            if (i % 5 === 4) {
                state = await page.evaluate(`document.title + ' | ' + location.href.slice(0, 70)`);
                console.log(`[${label}] wait ${i * 2}s: ${state}`);
            }
        } catch (e) {
            if (i % 5 === 4) console.log(`[${label}] wait ${i * 2}s: eval-fail ${String(e.message).slice(0, 60)}`);
        }
    }
    const info = await page.evaluate(`(() => {
    const hrefs = Array.from(document.querySelectorAll('div[data-index] a[href*="/zhaogong/"]'))
      .map(a => a.getAttribute('href')).filter(Boolean).slice(0, 3);
    const pagelinks = Array.from(document.querySelectorAll('a[href]'))
      .map(a => a.getAttribute('href'))
      .filter(h => h && (h.indexOf('page=') >= 0 || h.indexOf('pageNo') >= 0 || h.indexOf('下一页') >= 0 || h.indexOf('下一页') >= 0))
      .slice(0, 8);
    return { hrefs, pagelinks, title: document.title.slice(0, 40) };
  })()`).catch((e) => ({ hrefs: [], pagelinks: [], title: 'ERR: ' + e.message }));
    console.log(`[${label}] cards=${cards} title="${info.title}"`);
    console.log(`[${label}] first3=${JSON.stringify(info.hrefs)}`);
    console.log(`[${label}] pagelinks=${JSON.stringify(info.pagelinks)}`);
    return info;
}

const page = new Page('default');
const base = 'https://www.yupao.com/topic/a388c0/?keywords=' + encodeURIComponent('文员');

const p1 = await firstJobs(page, base, 'page1');
const p2 = await firstJobs(page, base + '&page=2', 'page2-param');
const same = JSON.stringify(p1.hrefs) === JSON.stringify(p2.hrefs);
console.log(`\n结论: ?page=2 ${same ? '无效果 (返回相同首屏)' : '有效! (返回不同数据)'}`);
process.exit(0);
