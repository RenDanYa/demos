
async function setTimeInterval() {
  const { currentFile } = this;
  const file = currentFile;
  const fileContent = await app.vault.cachedRead(file);
  const fileContentLines = fileContent.split("\n");

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

  // 如果没有找到完整的 frontmatter，返回错误
  if (frontmatterStart === -1 || frontmatterEnd === -1) {
    return "未找到有效的 frontmatter 区域";
  }

  // 提取 frontmatter 内容
  const frontmatterLines = fileContentLines.slice(frontmatterStart + 1, frontmatterEnd);
  
  // 查找 total_time 字段
  let totalTime = null;
  for (const line of frontmatterLines) {
    if (line.startsWith('total_time:')) {
      const match = line.match(/total_time:\s*([\d.]+)/);
      if (match) {
        totalTime = parseFloat(match[1]);
        break;
      }
    }
  }

  // 如果没有找到 total_time 字段，返回错误
  if (totalTime === null) {
    return "未找到 total_time 字段";
  }

  // 计算时间区间
  let timeQujian = '';
  
  if (totalTime < 8) {
    timeQujian = '0-8';
  } else if (totalTime >= 15) {
    timeQujian = '15+';
  } else {
    // 8 <= totalTime < 15，每个小时为一档
    const lowerBound = Math.floor(totalTime);
    const upperBound = lowerBound + 1;
    timeQujian = `${lowerBound}-${upperBound}`;
  }

  // 更新或添加 time_qujian 属性
  let timeQujianUpdated = false;
  const updatedFrontmatterLines = [];
  
  for (const line of frontmatterLines) {
    if (line.startsWith('time_qujian:')) {
      // 更新现有的 time_qujian 属性
      updatedFrontmatterLines.push(`time_qujian: ${timeQujian}`);
      timeQujianUpdated = true;
    } else {
      updatedFrontmatterLines.push(line);
    }
  }
  
  // 如果没有找到 time_qujian 属性，添加它
  if (!timeQujianUpdated) {
    updatedFrontmatterLines.push(`time_qujian: ${timeQujian}`);
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

  return timeQujian;
}

// 仅显示当前的时间区间而不修改文件
async function showTimeInterval() {
  const { currentFile } = this;
  const file = currentFile;
  const fileContent = await app.vault.cachedRead(file);
  const fileContentLines = fileContent.split("\n");

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

  // 如果没有找到完整的 frontmatter，返回错误
  if (frontmatterStart === -1 || frontmatterEnd === -1) {
    return "未找到有效的 frontmatter 区域";
  }

  // 提取 frontmatter 内容
  const frontmatterLines = fileContentLines.slice(frontmatterStart + 1, frontmatterEnd);
  
  // 查找 total_time 和 time_qujian 字段
  let totalTime = null;
  let currentTimeQujian = null;
  
  for (const line of frontmatterLines) {
    if (line.startsWith('total_time:')) {
      const match = line.match(/total_time:\s*([\d.]+)/);
      if (match) {
        totalTime = parseFloat(match[1]);
      }
    }
    if (line.startsWith('time_qujian:')) {
      const match = line.match(/time_qujian:\s*(.+)/);
      if (match) {
        currentTimeQujian = match[1].trim();
      }
    }
  }

  // 计算应设置的时间区间
  let recommendedTimeQujian = '';
  
  if (totalTime !== null) {
    if (totalTime < 8) {
      recommendedTimeQujian = '0-8';
    } else if (totalTime >= 15) {
      recommendedTimeQujian = '15+';
    } else {
      const lowerBound = Math.floor(totalTime);
      const upperBound = lowerBound + 1;
      recommendedTimeQujian = `${lowerBound}-${upperBound}`;
    }
  }

  // 返回显示信息
  let result = '';
  
  if (totalTime !== null) {
    result += `当前 total_time: ${totalTime} 小时\n`;
  } else {
    result += `当前 total_time: 未设置\n`;
  }
  
  if (currentTimeQujian !== null) {
    result += `当前 time_qujian: ${currentTimeQujian}\n`;
  } else {
    result += `当前 time_qujian: 未设置\n`;
  }
  
  if (totalTime !== null) {
    result += `推荐 time_qujian: ${recommendedTimeQujian}\n`;
  }
  
  // 显示规则说明
  result += `\n规则说明:\n`;
  result += `- total_time < 8: 0-8\n`;
  result += `- 8 ≤ total_time < 15: 向下取整后的小时区间\n`;
  result += `- total_time ≥ 15: 15+\n`;
  
  // 示例
  result += `\n示例:\n`;
  result += `- total_time: 7.5 → time_qujian: 0-8\n`;
  result += `- total_time: 8.05 → time_qujian: 8-9\n`;
  result += `- total_time: 10.3 → time_qujian: 10-11\n`;
  result += `- total_time: 14.8 → time_qujian: 14-15\n`;
  result += `- total_time: 15.2 → time_qujian: 15+\n`;

  return result;
}

exports.default = {
  name: "setTimeInterval",
  description: `根据 total_time 字段设置 time_qujian 属性

使用方法：
\`\`\`js
// 显示当前状态
showTimeInterval()
\`\`\`

\`\`\`js
// 直接设置 time_qujian 属性
setTimeInterval()
\`\`\`

规则：
- total_time < 8: time_qujian 设为 "0-8"
- 8 ≤ total_time < 15: 每个小时为一档，如 8.05 → "8-9", 10.3 → "10-11"
- total_time ≥ 15: time_qujian 设为 "15+"

示例：
- total_time: 7.5 → time_qujian: 0-8
- total_time: 8.05 → time_qujian: 8-9
- total_time: 10.3 → time_qujian: 10-11
- total_time: 14.8 → time_qujian: 14-15
- total_time: 15.2 → time_qujian: 15+
  `,
  entry: setTimeInterval,
  setTimeInterval: setTimeInterval,
  showTimeInterval: showTimeInterval
};
