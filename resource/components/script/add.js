function sumNumbers() {
  const args = Array.from(arguments);
  let total = 0;
  
  for (const arg of args) {
    const num = parseFloat(arg);
    if (!isNaN(num)) {
      total += num;
    }
  }
  
  // 保留两位小数
  return Math.round(total * 100) / 100;
}

// 带详细信息的版本
function sumNumbersDetailed() {
  const args = Array.from(arguments);
  let total = 0;
  let validNumbers = [];
  let invalidArgs = [];
  
  for (const arg of args) {
    const num = parseFloat(arg);
    if (!isNaN(num)) {
      total += num;
      validNumbers.push(num);
    } else {
      invalidArgs.push(arg);
    }
  }
  
  // 保留两位小数
  const roundedTotal = Math.round(total * 100) / 100;
  
  return {
    total: roundedTotal,
    validNumbers: validNumbers,
    invalidArgs: invalidArgs,
    validCount: validNumbers.length,
    invalidCount: invalidArgs.length
  };
}

exports.default = {
  name: "sumNumbers",
  description: `对多个参数进行求和计算，结果保留两位小数

直接调用方法：
\`\`\`js
// 简单求和，返回总和（保留两位小数）
sumNumbers(1, 2, 3.456, "4.5", "abc") // 返回 10.96

// 详细版本，返回包含详情的对象
sumNumbersDetailed(1, 2, 3.456, "4.5", "abc") 
// 返回: {
//   total: 10.96,
//   validNumbers: [1, 2, 3.456, 4.5],
//   invalidArgs: ["abc"],
//   validCount: 4,
//   invalidCount: 1
// }
\`\`\`

功能说明：
- 自动将参数转换为数字
- 忽略无法转换为数字的参数
- 支持整数和浮点数
- 结果保留两位小数
- 提供简单和详细两种版本
  `,
  entry: sumNumbers,
  sumNumbersDetailed: sumNumbersDetailed
};