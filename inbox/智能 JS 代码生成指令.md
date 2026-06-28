## **智能 JS 代码生成指令**

**场景定位：** [简单描述使用场景，例如："时间统计功能"、"数据计算"、"文件处理"]

**需求核心：**
- 主要功能：[一句话说明要做什么]
- 触发方式：[命令调用/按钮点击/自动执行]
- 数据来源：[当前文件/frontmatter/时间记录/其他]
- 输出结果：[修改文件/显示信息/返回数据]

**功能详情：**
1. [具体操作步骤1]
2. [具体操作步骤2]
3. [错误处理逻辑]

**接口要求：**
```
// 主函数格式：
async function functionName() {
  const { currentFile } = this;
  const file = currentFile;
  // 你的代码逻辑
}

// 显示函数格式（如需）：
async function showFunctionName() {
  // 只读逻辑，不修改文件
}

// 导出格式：
exports.default = {
  name: "功能名称",
  description: `功能描述和使用说明`,
  entry: 主函数名,
  其他函数名: 对应函数
};
```

**文件操作规范：**
- 读取文件：`await app.vault.cachedRead(file)`
- 写入文件：`await app.vault.modify(file, newContent)`
- Frontmatter 处理：找到 `---` 包裹区域进行解析
- 时间记录解析：以 `## 📝 时间记录` 为起始点
- 错误返回：使用 `return "错误信息"`

**参数示例：**
```
// 如果函数需要参数：
async function 函数名(param1, param2) {
  // 代码
}

// 调用示例：
函数名.call(this, '标签名', '属性名')
```

**特别说明：**
[任何特殊逻辑、边界情况、性能要求]

---

## **示例用法：**

**场景定位：** 睡眠时间统计功能

**需求核心：**
- 主要功能：统计时间记录中的睡眠时长，更新到 frontmatter
- 触发方式：命令调用
- 数据来源：时间记录部分的 #时间记录/休息/睡觉 标签
- 输出结果：更新 frontmatter 中的 sleep_time 属性

**功能详情：**
1. 找到时间记录部分，解析每行时间记录
2. 筛选出包含 #时间记录/休息/睡觉 标签的行
3. 计算总时长（分钟转换为小时，保留两位小数）
4. 更新 frontmatter 中的 sleep_time 属性
5. 提供只读显示函数

**接口要求：**
```
// 主函数：
async function updateSleepTime() {
  // 统计睡眠时间并更新 frontmatter
}

// 显示函数：
async function showSleepTime() {
  // 显示睡眠统计结果，不修改文件
}

// 导出：
exports.default = {
  name: "updateSleepTime",
  description: `统计睡眠时间并更新到 frontmatter`,
  entry: updateSleepTime,
  updateSleepTime: updateSleepTime,
  showSleepTime: showSleepTime
};
```

**文件操作规范：**
- 参考 updateTime.js 的时间记录解析逻辑
- 使用相同的 frontmatter 更新机制
- 错误时返回字符串信息

**特别说明：**
- 标签可能为 #时间记录/休息/睡觉 或 #时间记录/睡眠
- 需要处理跨午夜的睡眠时段（如 23:00-06:00）
- 提供 dv.paragraph 输出统计详情
