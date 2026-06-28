async function updateTime(tag, property) {
  const { currentFile } = this;
  const file = currentFile;
  const fileContent = await app.vault.cachedRead(file);
  const fileContentLines = fileContent.split("\n");

  // 找到时间记录部分
  const timeRecordStart = fileContentLines.findIndex(line => line.includes('## 📝 时间记录'));
  if (timeRecordStart === -1) {
    return "未找到时间记录部分";
  }

  let totalMinutes = 0;
  let matchedPeriods = [];

  // 解析时间记录，统计指定标签时长
  for (let i = timeRecordStart + 1; i < fileContentLines.length; i++) {
    const line = fileContentLines[i].trim();
    
    // 如果遇到下一个章节标题，停止解析
    if (line.startsWith('## ') && i > timeRecordStart + 1) {
      break;
    }

    // 匹配格式：- 06:04-06:25 起床 #时间记录/休息/起床
    const timeMatch = line.match(/-\s*(\d{2}:\d{2})-(\d{2}:\d{2})\s+(.+?)\s+#(.+)/);
    if (timeMatch) {
      const startTime = timeMatch[1];
      const endTime = timeMatch[2];
      const activity = timeMatch[3];
      const tags = timeMatch[4].split('/');

      // 检查是否包含指定标签
      if (tags.includes(tag)) {
        // 计算时长（分钟）
        const start = new Date(`2000-01-01 ${startTime}`);
        const end = new Date(`2000-01-01 ${endTime}`);
        const duration = (end - start) / (1000 * 60);
        totalMinutes += duration;
        matchedPeriods.push({
          start: startTime,
          end: endTime,
          activity: activity,
          duration: duration
        });
        
        console.log(`找到${tag}时间段: ${startTime}-${endTime}, 时长: ${duration}分钟`);
      }
    }
  }

  // 转换为小时（保留两位小数）
  const totalHours = Math.round((totalMinutes / 60) * 100) / 100;

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
  
  // 更新或添加指定属性
  let propertyUpdated = false;
  const updatedFrontmatterLines = [];
  
  for (const line of frontmatterLines) {
    if (line.startsWith(`${property}:`)) {
      // 更新现有的属性
      updatedFrontmatterLines.push(`${property}: ${totalHours}`);
      propertyUpdated = true;
    } else {
      updatedFrontmatterLines.push(line);
    }
  }
  
  // 如果没有找到属性，添加它
  if (!propertyUpdated) {
    updatedFrontmatterLines.push(`${property}: ${totalHours}`);
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

  return totalHours;
}

// 仅显示统计结果而不修改文件
async function showTime(tag, property) {
  const { currentFile } = this;
  const file = currentFile;
  const fileContent = await app.vault.cachedRead(file);
  const fileContentLines = fileContent.split("\n");

  const timeRecordStart = fileContentLines.findIndex(line => line.includes('## 📝 时间记录'));
  if (timeRecordStart === -1) {
    return "未找到时间记录部分";
  }

  let totalMinutes = 0;
  let matchedPeriods = [];

  for (let i = timeRecordStart + 1; i < fileContentLines.length; i++) {
    const line = fileContentLines[i].trim();
    
    if (line.startsWith('## ') && i > timeRecordStart + 1) {
      break;
    }

    // 匹配格式：- 06:04-06:25 起床 #时间记录/休息/起床
    const timeMatch = line.match(/-\s*(\d{2}:\d{2})-(\d{2}:\d{2})\s+(.+?)\s+#(.+)/);
    if (timeMatch) {
      const startTime = timeMatch[1];
      const endTime = timeMatch[2];
      const activity = timeMatch[3];
      const tags = timeMatch[4].split('/');

      if (tags.includes(tag)) {
        const start = new Date(`2000-01-01 ${startTime}`);
        const end = new Date(`2000-01-01 ${endTime}`);
        const duration = (end - start) / (1000 * 60);
        totalMinutes += duration;
        matchedPeriods.push({
          start: startTime,
          end: endTime,
          activity: activity,
          duration: duration
        });
      }
    }
  }

  const totalHours = Math.round((totalMinutes / 60) * 100) / 100;
  
  // 获取当前的属性值
  const cache = app.metadataCache.getFileCache(file);
  const currentValue = cache?.frontmatter?.[property] || '未设置';
  
  // 显示统计结果
  dv.paragraph(`**${tag}时长统计**: ${totalHours}小时 (${totalMinutes}分钟)`);
  dv.paragraph(`**当前 ${property} 属性**: ${currentValue}`);
  
  // 显示匹配时段详情
  if (matchedPeriods.length > 0) {
    dv.paragraph(`**${tag}时段详情**:`);
    for (const period of matchedPeriods) {
      dv.paragraph(`- ${period.start}-${period.end} ${period.activity} (${Math.round(period.duration)}分钟)`);
    }
  }
  
  // 创建一个按钮来触发更新
  const button = document.createElement('button');
  button.textContent = `更新 ${property} 属性`;
  button.style.marginTop = '10px';
  button.onclick = async () => {
    const result = await updateTime.call(this, tag, property);
    dv.paragraph(result);
  };
  
  return button;
}

// 保持向后兼容的原有函数
async function updateWorkTime() {
  return await updateTime.call(this, '工作', 'work_time');
}

async function showWorkTime() {
  return await showTime.call(this, '工作', 'work_time');
}

exports.default = {
  name: "updateTime",
  description: `读取时间记录中指定标签的时长并更新到指定属性

使用方法：
\`\`\`js
// 显示统计结果并提供更新按钮
showTime('标签名', '属性名')
\`\`\`

\`\`\`js
// 直接更新属性
updateTime('标签名', '属性名')
\`\`\`

示例：
\`\`\`js
// 更新运动时长
showTime('运动', 'sport_time')
updateTime('运动', 'sport_time')

// 更新阅读时长  
showTime('阅读', 'read_time')
updateTime('阅读', 'read_time')

// 向后兼容的原有方法（工作相关）
showWorkTime()
updateWorkTime()
\`\`\`
  `,
  entry: updateTime,
  updateTime: updateTime,
  showTime: showTime,
  // 保持向后兼容
  updateWorkTime: updateWorkTime,
  showWorkTime: showWorkTime
};