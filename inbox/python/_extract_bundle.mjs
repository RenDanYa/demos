import { readFileSync } from 'node:fs';

const file = 'd:/obsidian/demo/inbox/python/_yupao_bundles/319-07d1f5213c9f2e9b.js';
const src = readFileSync(file, 'utf-8');

for (const pos of [25104, 56007, 62413, 113341]) {
    console.log(`\n===== infinite @ ${pos} =====`);
    console.log(src.slice(pos - 500, pos + 500));
}
