async function getTagDuration(targetTag) {
  const { currentFile } = this;
  const file = currentFile;
  const cache = app.metadataCache.getFileCache(file);
  const fileContent = await app.vault.cachedRead(file);
  const fileContentLines = fileContent.split("\n");

  // 找到时间记录部分
  const timeRecordStart = fileContentLines.findIndex(line => line.includes('## 📝 时间记录'));
  if (timeRecordStart === -1) {
    return "未找到时间记录部分";
  }

  let totalMinutes = 0;

  // 从时间记录部分开始解析
  for (let i = timeRecordStart + 1; i < fileContentLines.length; i++) {
    const line = fileContentLines[i].trim();
    
    // 如果遇到下一个章节标题，停止解析
    if (line.startsWith('## ') && i > timeRecordStart + 1) {
      break;
    }

    // 匹配时间记录格式：HH:mm - HH:mm 活动 #标签
    const timeMatch = line.match(/(\d{2}:\d{2}) - (\d{2}:\d{2}) (.+?) #(.+)/);
    if (timeMatch) {
      const startTime = timeMatch[1];
      const endTime = timeMatch[2];
      const tags = timeMatch[4].split('/');

      // 计算时长（分钟）
      const start = new Date(`2000-01-01 ${startTime}`);
      const end = new Date(`2000-01-01 ${endTime}`);
      const duration = (end - start) / (1000 * 60);

      // 检查是否包含目标标签
      if (tags.includes(targetTag)) {
        totalMinutes += duration;
      }
    }
  }

  // 格式化输出
  const hours = Math.floor(totalMinutes / 60);
  const minutes = Math.round(totalMinutes % 60);
  
  if (hours > 0) {
    return minutes > 0 ? `${hours}小时${minutes}分钟` : `${hours}小时`;
  } else {
    return `${minutes}分钟`;
  }
}

// 获取所有标签的统计（可选功能）
async function getAllTagDurations() {
  const { currentFile } = this;
  const file = currentFile;
  const cache = app.metadataCache.getFileCache(file);
  const fileContent = await app.vault.cachedRead(file);
  const fileContentLines = fileContent.split("\n");

  const timeRecordStart = fileContentLines.findIndex(line => line.includes('## 📝 时间记录'));
  if (timeRecordStart === -1) {
    return "未找到时间记录部分";
  }

  const tagDurations = {};

  for (let i = timeRecordStart + 1; i < fileContentLines.length; i++) {
    const line = fileContentLines[i].trim();
    
    if (line.startsWith('## ') && i > timeRecordStart + 1) {
      break;
    }

    const timeMatch = line.match(/(\d{2}:\d{2}) - (\d{2}:\d{2}) (.+?) #(.+)/);
    if (timeMatch) {
      const startTime = timeMatch[1];
      const endTime = timeMatch[2];
      const tags = timeMatch[4].split('/');

      const start = new Date(`2000-01-01 ${startTime}`);
      const end = new Date(`2000-01-01 ${endTime}`);
      const duration = (end - start) / (1000 * 60);

      // 为每个标签累加时长
      tags.forEach(tag => {
        if (!tagDurations[tag]) {
          tagDurations[tag] = 0;
        }
        tagDurations[tag] += duration;
      });
    }
  }

  // 格式化结果
  const result = {};
  Object.entries(tagDurations).forEach(([tag, minutes]) => {
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    result[tag] = hours > 0 ? `${hours}小时${mins}分钟` : `${mins}分钟`;
  });

  return result;
}

exports.default = {
  name: "getTagDuration",
  description: `获取指定标签在时间记录中的总时长

使用方法：
\`\`\`js
// 获取单个标签时长
getTagDuration('工作')
\`\`\`

\`\`\`js
// 获取所有标签时长统计
getAllTagDurations()
\`\`\`
  `,
  entry: getTagDuration,
  // 可选：导出第二个函数
  getAllTagDurations: getAllTagDurations
};