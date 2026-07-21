---
name: "todo-result"
description: "Reorganizes and integrates messy todo lists by timeline/flow stages, merges duplicates, sorts time-anchored items chronologically, and adds priority/time labels. Invoke when user asks to reorganize, integrate, deduplicate, restructure, or regroup todo files with timeline grouping (e.g., 前期准备→执行中→收尾)."
---

# Todo Result (待办清单整合重组)

Reorganize a bloated or duplicated todo list into a clean, timeline-based structure with merged duplicates, **chronologically sorted time-anchored items**, priority/time-node labels, and bold emphasis on key items.

## When to Invoke

Invoke this skill when the user asks to:
- 重新整合 / 重组 / 重构 待办清单
- 按时间线 / 流程阶段 分组待办
- 合并重复项 / 去重待办
- 标注优先级 / 时间节点
- 重点关注加粗
- 按时间顺序排列待办

Trigger phrases include: "重新整合待办清单", "按时间线分组", "合并重复项", "去重", "标注优先级", "流程阶段重新分组", "前期准备 → 执行中 → 收尾", "有时间要求的待办按顺序排列".

## Workflow

### Step 1 — Read & Analyze Source File

1. Use the `Read` tool to load the target todo file (typically a Markdown file under `待办/`).
2. Identify the existing structure:
   - Frontmatter (preserve `tags`, `theme`, `created`, `source_count`, `original_tasks`, `deduplicated_tasks`).
   - `# 原待办` section with `![[笔记名#待办]]` embeds — **keep this section unchanged** (it is the source-of-truth reference).
   - `# 整合后待办` section — this is what we rewrite.
3. Scan for duplicate / highly similar tasks across sections (common duplicates: 试纱费, 押金, 破损赔偿, 改尺寸, 品牌授权核查, 场地照片携带).

### Step 2 — Define Timeline Stages

Group all tasks into **three timeline stages** (adapt stage names to the domain if needed):

| Stage | Default Name | Typical Time Window |
|-------|--------------|---------------------|
| 1 | 前期准备 | 婚礼前 6-10 个月 (or domain equivalent) |
| 2 | 执行中 | 试纱当天 + 定纱签约 (the core execution day) |
| 3 | 收尾 | 定纱后 + 取还纱 + 婚礼当天 |

> If the domain is not wedding-related, rename stages to fit (e.g., 需求确认 → 开发执行 → 上线收尾). Keep the three-stage structure.

### Step 3 — Merge Duplicates

For each task cluster:
- Keep only **one** canonical item; merge similar phrasings into a single line.
- Preserve the most actionable / specific phrasing.
- When a parent task has sub-details, nest them as indented checkboxes `- [ ] sub-item`.
- Move each merged task into the stage it logically belongs to (not where it originally appeared).

### Step 4 — Add Labels & Emphasis

Apply three label types at the start of task lines (after the `- [ ]`):

| Label | Meaning | When to apply |
|-------|---------|---------------|
| ⏰ | 关键时间节点 | Time-sensitive items: deadlines, booking windows, "提前 X 个月" |
| ⭐ | 必备项 | Cannot-be-missed core items: budget, date, key purchases, contract signing |
| 🔍 | 关键检查点 | Verification/avoid-pit items: authorization checks, damage inspection, contract clauses |

Labels can be combined (e.g., `⏰⭐`).

**Bold emphasis**: wrap key phrases in `**...**` — especially for:
- **确定婚期** / **确定预算** / **确定场地**
- **第一次试纱** / **第二次试纱** (stage milestones)
- **明确租赁款式** / **签订完整合同**
- Any user-specified must-bold item.

### Step 5 — Chronological Sorting of Time-Anchored Items (NEW)

Within each sub-stage, **items with explicit time anchors must be sorted in chronological order** — from the earliest (farthest from the event) to the latest (closest to the event / day-of).

#### 5.1 What counts as a time anchor

An item is "time-anchored" if it contains any of:
- An absolute time: `婚礼前 X 个月/周/天`, `婚前 X 天`, `婚礼当天`, `婚礼前一天`
- A relative lead time: `提前 X 个月/周/天`, `提前 X 小时`
- A sequence marker tied to a milestone: `第一次试纱`, `第二次试纱`, `定纱后`, `取纱当天`, `归还时`
- An event-day phase: `出行前`, `到店时`, `试纱当天`, `收货当天`

#### 5.2 Sort order (descending distance from wedding → ascending closeness)

Sort time-anchored items **from farthest to closest** relative to the wedding day. Canonical ordering scale (use as the reference ladder):

```
婚礼前 8-10 个月  >  婚礼前 6-8 个月  >  婚礼前 3-6 个月  >  婚礼前 3-4 个月
>  婚礼前 1-2 个月  >  提前 1-2 周  >  提前 1-3 天
>  出行前 / 到店时 (day-of)  >  试纱当天 (during)
>  定纱后  >  婚礼前 1 个月 (复尺)  >  婚礼前 1-2 天 (量体)
>  婚礼前一天  >  婚礼当天  >  婚礼第二天 (归还)
```

> Adapt the ladder to the domain. The principle is always: **earliest action first, day-of / closing action last**.

#### 5.3 Placement of non-time-anchored items

- Items **without** a specific time anchor (e.g., "选择工作日", "预留 2-3 小时", "准备胸贴") are placed **after** all time-anchored items in the same sub-stage, grouped logically (preparation items → day-of execution items → verification items).
- If a non-anchored item is a prerequisite for a time-anchored one (e.g., "预约多家店" must happen before "提前 1-3 天确认预约"), place it just before the dependent anchored item.

#### 5.4 Worked example (from 婚纱.md §1.4)

**Before (unordered)** — time anchors jump back and forth:
```
- [ ] ⏰⭐ **第一次试纱**：婚礼前 3-4 个月 …
- [ ] ⏰⭐ **第二次试纱**：婚礼前 1-2 个月 …
- [ ] 提前 1-2 周预约并告知场地风格 …
- [ ] ⏰ 提前 1-3 天确认预约，准时到达
- [ ] 选择工作日 … 预约多家婚纱店          ← belongs earlier (when booking)
- [ ] 🔍 出行前确认试纱档期和租赁档期        ← day-of
- [ ] 预留 2-3 小时试纱时间                 ← during
```

**After (chronologically sorted)**:
```
- [ ] ⏰⭐ **第一次试纱**：婚礼前 3-4 个月，确定婚纱店和风格方向
- [ ] ⏰⭐ **第二次试纱**：婚礼前 1-2 个月，结合最终身材和场布定稿选定婚纱
- [ ] 选择工作日 / 淡季，预约多家婚纱店（建议 3-5 家）        ← non-anchored prerequisite, placed before the booking confirmation
- [ ] 提前 1-2 周预约并告知场地风格、预算和身材特点
- [ ] ⏰ 提前 1-3 天确认预约，准时到达
- [ ] 🔍 出行前确认试纱档期和租赁档期                       ← day-of verification
- [ ] 预留 2-3 小时试纱时间                                 ← during execution
```

#### 5.5 Self-check

After sorting, verify the time anchors read as a **monotonic countdown** (each line's anchor is ≤ the previous line's anchor in distance-from-wedding). If any line breaks the countdown, reorder.

### Step 6 — Write Output File

1. Preserve the original frontmatter; add/update these fields:
   - `updated: <current timestamp>`
   - `reorganized: <current date>`
   - `reorganization: 按时间线/流程阶段重新分组（前期准备→执行中→收尾），合并重复项，时间锚点按时间顺序排列，标注优先级/时间节点`
2. Keep the `# 原待办` section **byte-for-byte unchanged** (it holds the `![[...]]` embeds).
3. Replace the `# 整合后待办` section with the new three-stage, chronologically-sorted structure.
4. Prepend a label legend blockquote right after the `# 整合后待办` heading.
5. Append a `## 整合说明` section at the end documenting what was merged, how labels were applied, and that time-anchored items were sorted chronologically.
6. Use the `Write` tool to overwrite the original file (user already has it open; they expect in-place reorganization).

## Output Structure Template

```markdown
---
<original frontmatter, with updated/reorganized fields added>
---

# 原待办

> <unchanged — keep all ![[笔记名#待办]] embeds>

# 整合后待办

> **标签说明**：⏰ 关键时间节点 ｜ ⭐ 必备项 ｜ 🔍 关键检查点
>
> **流程阶段**：一、前期准备（<time window>）→ 二、执行中（<execution scope>）→ 三、收尾（<closing scope>）
>
> **排序规则**：同一子阶段内，带时间锚点的待办按时间顺序排列（由远及近），无时间锚点的待办置于其后

---

## 一、前期准备（<time window>）

### 1.1 <sub-stage>
- [ ] ⏰⭐ **确定婚期** — <detail>
- [ ] ⭐ **确定预算与心理价位** — <detail>
- [ ] 🔍 <verification item>
	- [ ] <sub-detail>
	- [ ] <sub-detail>

### 1.2 <sub-stage with time-anchored items — sorted chronologically>
- [ ] ⏰⭐ **第一次试纱**：婚礼前 3-4 个月 …
- [ ] ⏰⭐ **第二次试纱**：婚礼前 1-2 个月 …
- [ ] <non-anchored prerequisite, e.g. 预约多家店>
- [ ] ⏰ 提前 1-2 周 …
- [ ] ⏰ 提前 1-3 天 …
- [ ] 🔍 出行前 …
- [ ] 预留 2-3 小时 …

---

## 二、执行中（<execution scope>）

### 2.1 <sub-stage>
...

---

## 三、收尾（<closing scope>）

### 3.1 <sub-stage>
...

---

## 整合说明

> **本次重组要点**：
> 1. **按时间线分三大阶段**：...
> 2. **合并重复项**：<list which duplicate clusters were merged>
> 3. **时间锚点排序**：同一子阶段内带时间要求的待办按时间顺序（由远及近）排列，无时间锚点的置于其后
> 4. **优先级/时间节点标签**：⏰ / ⭐ / 🔍
> 5. **重点关注加粗**：<list bolded items>
```

## Rules & Constraints

- **Never drop tasks** — every original actionable item must appear (merged) in the output.
- **Never edit the `# 原待办` section** — it holds the source embeds that are the single source of truth.
- **Preserve frontmatter** except for the added reorganization metadata fields.
- **Keep nesting shallow** — at most 2 levels of indented checkboxes (`- [ ]` then `\t- [ ]`).
- **Labels go before bold** — order: `- [ ] ⏰⭐ **keyword** — detail`.
- **Chronological sort is mandatory for time-anchored items** — within each sub-stage, items with explicit time anchors (⏰ label or text like "提前 X", "婚礼前 X") must be sorted from earliest to latest (farthest from wedding → day-of). Non-anchored items follow after, grouped logically. (See Step 5.)
- **Language**: match the source file's language (typically Chinese for this workspace).
- **No emojis in prose** except the three defined labels (⏰⭐🔍) and the 💡 tip marker.
- If the user specifies extra bold items (e.g., "重点关注增加加粗（**确定婚期**）"), always honor their explicit list.

## Domain Adaptation

The default domain is wedding-preparation todos (婚纱/婚庆/婚鞋/婚纱照). The three-stage structure (前期准备 → 执行中 → 收尾) is generic enough for any project todo file. When adapting:

- **婚纱 / 婚纱租赁**: stages stay as 前期准备 → 试纱执行 → 定纱收尾. Time ladder: 婚礼前 6-10 个月 → 3-4 个月 → 1-2 个月 → 1-2 周 → 1-3 天 → 出行前 → 试纱当天 → 定纱后 → 取纱 → 婚礼当天 → 归还.
- **婚庆**: stages become 前期沟通 → 谈判执行 → 签约收尾. Time ladder anchored to 婚期/签约日.
- **婚纱照**: stages become 拍摄前准备 → 拍摄当天 → 选片后期. Time ladder anchored to 拍摄日.
- **Generic project**: rename to 需求确认 → 执行中 → 上线收尾. Time ladder anchored to 上线日 / 交付日.

## Verification

After writing, confirm:
1. Task count in new structure ≈ original `deduplicated_tasks` (no silent drops).
2. All `![[...]]` embeds in `# 原待办` are untouched.
3. Every stage heading uses `##` and every sub-stage uses `###`.
4. Labels (⏰⭐🔍) appear on at least the key milestone items.
5. User-specified bold items (e.g., **确定婚期**) are bolded.
6. **Within each sub-stage, time-anchored items are sorted chronologically (earliest → latest / farthest from event → day-of). The time anchors read as a monotonic countdown.** (See Step 5.5.)
