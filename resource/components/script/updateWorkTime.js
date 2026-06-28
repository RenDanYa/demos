async function updateWorkTime() {
  const { currentFile } = this;
  const file = currentFile;
  const fileContent = await app.vault.cachedRead(file);
  const fileContentLines = fileContent.split("\n");

  // 找到时间记录部分
  const timeRecordStart = fileContentLines.findIndex(line => line.includes('## 📝 时间记录'));
  if (timeRecordStart === -1) {
    return "未找到时间记录部分";
  }

  let workMinutes = 0;

  // 解析时间记录，统计工作标签时长
  for (let i = timeRecordStart + 1; i < fileContentLines.length; i++) {
    const line = fileContentLines[i].trim();
    
    // 如果遇到下一个章节标题，停止解析
    if (line.startsWith('## ') && i > timeRecordStart + 1) {
      break;
    }

    // 新的正则表达式匹配格式：- 06:04-06:25 起床 #时间记录/休息/起床
    const timeMatch = line.match(/-\s*(\d{2}:\d{2})-(\d{2}:\d{2})\s+(.+?)\s+#(.+)/);
    if (timeMatch) {
      const startTime = timeMatch[1];
      const endTime = timeMatch[2];
      const tags = timeMatch[4].split('/');

      // 检查是否包含工作标签
      if (tags.includes('工作')) {
        // 计算时长（分钟）
        const start = new Date(`2000-01-01 ${startTime}`);
        const end = new Date(`2000-01-01 ${endTime}`);
        const duration = (end - start) / (1000 * 60);
        workMinutes += duration;
        
        console.log(`找到工作时间段: ${startTime}-${endTime}, 时长: ${duration}分钟`);
      }
    }
  }

  // 转换为小时（保留两位小数）
  const workHours = Math.round((workMinutes / 60) * 100) / 100;

  // 找到 frontmatter 的开始和结束位置
  let frontmatterStart = -1;
  let frontmatterEnd = -1;
  
  for (let i = 0; i < fileContentLines.length; i++) {
    if (fileContentLines[i].trim() === '---') {
      if (frontmatterStart === -1) {
        frontmatterStart = i;
      } else {
        frontmatterEnd = i;
        break;
      }
    }
  }

  // 如果没有找到完整的 frontmatter，创建一个新的
  if (frontmatterStart === -1 || frontmatterEnd === -1) {
    return "未找到有效的 frontmatter 区域";
  }

  // 提取 frontmatter 内容
  const frontmatterLines = fileContentLines.slice(frontmatterStart + 1, frontmatterEnd);
  
  // 更新或添加 work_time 属性
  let workTimeUpdated = false;
  const updatedFrontmatterLines = [];
  
  for (const line of frontmatterLines) {
    if (line.startsWith('work_time:')) {
      // 更新现有的 work_time
      updatedFrontmatterLines.push(`work_time: ${workHours}`);
      workTimeUpdated = true;
    } else {
      updatedFrontmatterLines.push(line);
    }
  }
  
  // 如果没有找到 work_time 属性，添加它
  if (!workTimeUpdated) {
    updatedFrontmatterLines.push(`work_time: ${workHours}`);
  }

  // 重建文件内容
  const newFileContent = [
    '---',
    ...updatedFrontmatterLines,
    '---',
    ...fileContentLines.slice(frontmatterEnd + 1)
  ].join('\n');

  // 保存文件
  await app.vault.modify(file, newFileContent);

  return `已更新 work_time: ${workHours}小时 (${workMinutes}分钟)`;
}

// 仅显示统计结果而不修改文件
async function showWorkTime() {
  const { currentFile } = this;
  const file = currentFile;
  const fileContent = await app.vault.cachedRead(file);
  const fileContentLines = fileContent.split("\n");

  const timeRecordStart = fileContentLines.findIndex(line => line.includes('## 📝 时间记录'));
  if (timeRecordStart === -1) {
    return "未找到时间记录部分";
  }

  let workMinutes = 0;
  let workPeriods = [];

  for (let i = timeRecordStart + 1; i < fileContentLines.length; i++) {
    const line = fileContentLines[i].trim();
    
    if (line.startsWith('## ') && i > timeRecordStart + 1) {
      break;
    }

    // 新的正则表达式匹配格式：- 06:04-06:25 起床 #时间记录/休息/起床
    const timeMatch = line.match(/-\s*(\d{2}:\d{2})-(\d{2}:\d{2})\s+(.+?)\s+#(.+)/);
    if (timeMatch) {
      const startTime = timeMatch[1];
      const endTime = timeMatch[2];
      const activity = timeMatch[3];
      const tags = timeMatch[4].split('/');

      if (tags.includes('工作')) {
        const start = new Date(`2000-01-01 ${startTime}`);
        const end = new Date(`2000-01-01 ${endTime}`);
        const duration = (end - start) / (1000 * 60);
        workMinutes += duration;
        workPeriods.push({
          start: startTime,
          end: endTime,
          activity: activity,
          duration: duration
        });
      }
    }
  }

  const workHours = Math.round((workMinutes / 60) * 100) / 100;
  
  // 获取当前的 work_time 值
  const cache = app.metadataCache.getFileCache(file);
  const currentWorkTime = cache?.frontmatter?.work_time || '未设置';
  
  // 显示统计结果
  dv.paragraph(`**工作时长统计**: ${workHours}小时 (${workMinutes}分钟)`);
  dv.paragraph(`**当前 work_time 属性**: ${currentWorkTime}`);
  
  // 显示工作时段详情
  if (workPeriods.length > 0) {
    dv.paragraph("**工作时段详情**:");
    for (const period of workPeriods) {
      dv.paragraph(`- ${period.start}-${period.end} ${period.activity} (${Math.round(period.duration)}分钟)`);
    }
  }
  
  // 创建一个按钮来触发更新
  const button = document.createElement('button');
  button.textContent = '更新 work_time 属性';
  button.style.marginTop = '10px';
  button.onclick = async () => {
    const result = await updateWorkTime.call(this);
    dv.paragraph(result);
  };
  
  return button;
}

exports.default = {
  name: "updateWorkTime",
  description: `读取时间记录中的工作标签时长并更新到work_time属性

使用方法：
\`\`\`js
// 显示统计结果并提供更新按钮
showWorkTime()
\`\`\`

\`\`\`js
// 直接更新work_time属性
updateWorkTime()
\`\`\`
  `,
  entry: updateWorkTime,
  showWorkTime: showWorkTime
};