---
file_name: <% tp.date.now("WW_YYYY_MM_DD") %>.md
month: <% tp.date.now("MM") %>
week: <% tp.date.now("WW") %>
created: <% tp.date.now("YYYY-MM-DD") %>
sleep_time: <% await tp.system.prompt("起床时间", "") %>
day_of_week: <% (tp.date.now("d") == 0 ? 7 : tp.date.now("d")) %>
work_time:
work_content:
morning_mood:
afternoon_mood:
tags:
  - daily
weight: 
typing_speed: 
bedtime:
---

![[<% tp.date.now("YYYY-WW") %>#🎯 本周目标]]

## 📝 时间记录


## 📊 分时段追踪表

| 时间段         | 精力值 (1-10) | 活动内容 | 备注  |
| ----------- | ---------- | ---- | --- |
| 07:00-08:00 |            |      |     |
| 08:30-09:00 |            |      |     |
| 09:00-11:00 |            |      |     |
| 11:00-11:40 |            |      |     |
| 12:10-13:00 |            |      |     |
| 14:30-16:00 |            |      |     |
| 16:00-18:00 |            |      |     |



## 🔁 每日习惯
- [ ] 👣 运动 #习惯/运动 ⏰ <% tp.date.now("YYYY-MM-DD") %> 18:00 📅 <% tp.date.now("YYYY-MM-DD") %>
- [ ] 📻 播客 #习惯/播客 ⏰ <% tp.date.now("YYYY-MM-DD") %> 22:00 📅 <% tp.date.now("YYYY-MM-DD") %>
- [ ] 📓 执行待办 ⏰ <% tp.date.now("YYYY-MM-DD") %> 8:40 📅 <% tp.date.now("YYYY-MM-DD") %>
- [ ] 🪄 模型打卡 #习惯/日记 ⏰ <% tp.date.now("YYYY-MM-DD") %> 20:00 📅 <% tp.date.now("YYYY-MM-DD") %>
- [ ] 📚 阅读 #习惯/阅读 ⏰ <% tp.date.now("YYYY-MM-DD") %> 20:30 📅 <% tp.date.now("YYYY-MM-DD") %>
- [ ] 🔍[[每日行动追踪|SOP填写]] ⏰ <% tp.date.now("YYYY-MM-DD") %> 23:00 📅 <% tp.date.now("YYYY-MM-DD") %>
- [ ] 🛏️上床睡觉+修改阅读标签内容 ⏰ <% tp.date.now("YYYY-MM-DD") %> 23:25 📅 <% tp.date.now("YYYY-MM-DD") %>
<%*
// 获取当前日期信息
let now = new Date();
let dayOfWeek = now.getDay();
let year = now.getFullYear();
let month = now.getMonth() + 1; // 月份从0开始，所以要+1
let date = now.getDate();

// 判断是否是当月最后一天
let isLastDayOfMonth = false;
let nextDay = new Date(now);
nextDay.setDate(nextDay.getDate() + 1);
if (nextDay.getMonth() !== now.getMonth()) {
    isLastDayOfMonth = true;
}

// 只在周日添加每周复盘
if (date % 15 === 0) {
    tR += `- [ ] 💫 每周复盘-复盘 #习惯/周复盘 ⏰ ${tp.date.now("YYYY-MM-DD")} 08:30 📅 ${tp.date.now("YYYY-MM-DD")}\n`;
	tR += `- [ ] ⌨️ 打字 #习惯/打字 ⏰ ${tp.date.now("YYYY-MM-DD")} 20:20 📅  ${tp.date.now("YYYY-MM-DD")}\n`;
	tR += `- [ ] 🧠 分配待办 #习惯/日记 ⏰ ${tp.date.now("YYYY-MM-DD")} 19:15 📅  ${tp.date.now("YYYY-MM-DD")}\n`;
	tR += `- [ ] 💢 分析偏差 #习惯/日记 ⏰ ${tp.date.now("YYYY-MM-DD")} 19:30 📅  ${tp.date.now("YYYY-MM-DD")}\n`;
}

// 在每月最后一天添加每月复盘
if (isLastDayOfMonth) {
    tR += `- [ ] 🔆 每月复盘 #习惯/月复盘 ⏰ ${tp.date.now("YYYY-MM-DD")} 09:00 📅 ${tp.date.now("YYYY-MM-DD")}\n`;
}

if (dayOfWeek === 0) {
    tR += `- [ ] 🏘️ 打扫+听播客 ⏰ ${tp.date.now("YYYY-MM-DD")} 20:30 📅 ${tp.date.now("YYYY-MM-DD")}\n`;
}

// 在日期为3的倍数时添加洗澡打卡
if (date % 3 === 2) {
    tR += `- [ ] 🚿 洗澡打卡+去黑头 ⏰ ${tp.date.now("YYYY-MM-DD")} 20:20 📅 ${tp.date.now("YYYY-MM-DD")}\n`;
}

%>
## 🛏️每日整理仪式





