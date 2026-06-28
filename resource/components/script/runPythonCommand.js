function runPythonFile() {
  const args = Array.from(arguments);
  let filePath = '';
  let options = {
    timeout: 10000,
    returnDetailed: false,
    args: []
  };
  
  // 解析参数
  for (const arg of args) {
    if (typeof arg === 'string') {
      filePath = arg;
    } else if (typeof arg === 'object') {
      options = { ...options, ...arg };
    }
  }
  
  if (!filePath) {
    throw new Error('No Python file path provided');
  }
  
  // 检查文件是否存在
  const fs = require('fs');
  if (!fs.existsSync(filePath)) {
    throw new Error(`Python file not found: ${filePath}`);
  }
  
  // 确保文件扩展名是.py
  if (!filePath.endsWith('.py')) {
    throw new Error('File must be a Python file (.py)');
  }
  
  try {
    const startTime = Date.now();
    const path = require('path');
    
    // 构建命令：python file.py [args...]
    const commandArgs = [filePath, ...options.args];
    const { execSync } = require('child_process');
    const result = execSync(`python "${commandArgs.join('" "')}"`, {
      encoding: 'utf8',
      timeout: options.timeout,
      cwd: path.dirname(filePath)
    });
    
    const executionTime = Date.now() - startTime;
    
    if (options.returnDetailed) {
      return {
        success: true,
        output: result.trim(),
        executionTime: executionTime,
        filePath: filePath,
        args: options.args
      };
    } else {
      return result.trim();
    }
    
  } catch (error) {
    if (options.returnDetailed) {
      return {
        success: false,
        error: error.message,
        executionTime: Date.now() - startTime,
        filePath: filePath,
        args: options.args
      };
    } else {
      throw new Error(`Python execution failed: ${error.message}`);
    }
  }
}

// 检查Python是否可用
function checkPythonAvailable() {
  try {
    const { execSync } = require('child_process');
    execSync('python --version', { stdio: 'pipe' });
    return { available: true, version: execSync('python --version', { encoding: 'utf8' }).trim() };
  } catch (error) {
    try {
      execSync('python3 --version', { stdio: 'pipe' });
      return { available: true, version: execSync('python3 --version', { encoding: 'utf8' }).trim() };
    } catch (error2) {
      return { available: false, error: 'Python is not installed or not in PATH' };
    }
  }
}

// 主入口函数 - 支持多种操作
function pythonEntry() {
  const args = Array.from(arguments);
  
  // 如果没有参数，显示帮助信息
  if (args.length === 0) {
    return {
      help: "Python Runner - 可用命令:",
      commands: {
        "run <file> [options]": "运行Python文件",
        "check": "检查Python环境",
        "code <python_code>": "运行Python代码字符串"
      },
      example: "pythonEntry('run', 'script.py', {args: ['param1']})"
    };
  }
  
  const command = args[0];
  
  switch (command) {
    case 'run':
    case 'file':
      // 运行Python文件: pythonEntry('run', 'file.py', {options})
      const filePath = args[1];
      const options = args[2] || {};
      return runPythonFile(filePath, options);
      
    case 'check':
    case 'env':
      // 检查环境: pythonEntry('check')
      return checkPythonAvailable();
      
    case 'code':
    case 'eval':
      // 运行代码字符串: pythonEntry('code', 'print("Hello")')
      const pythonCode = args[1];
      const codeOptions = args[2] || {};
      
      // 创建临时文件执行
      const fs = require('fs');
      const path = require('path');
      const tempFileName = `temp_python_${Date.now()}.py`;
      const tempFilePath = path.join(__dirname, tempFileName);
      
      try {
        fs.writeFileSync(tempFilePath, pythonCode);
        const result = runPythonFile(tempFilePath, codeOptions);
        
        // 清理临时文件
        fs.unlinkSync(tempFilePath);
        
        return result;
      } catch (error) {
        // 确保清理临时文件
        if (fs.existsSync(tempFilePath)) {
          fs.unlinkSync(tempFilePath);
        }
        throw error;
      }
      
    default:
      // 如果没有识别命令，尝试作为文件路径直接运行
      if (typeof command === 'string' && command.endsWith('.py')) {
        return runPythonFile(command, args[1] || {});
      } else {
        throw new Error(`未知命令: ${command}. 使用 pythonEntry() 查看帮助。`);
      }
  }
}

exports.default = {
  name: "runPython",
  description: `运行Python文件或代码字符串

直接调用方法：
\`\`\`js
// 运行Python文件（最简单的方式）
runPython('D:/obsidian/demo/inbox/python/convert_table_to_list_general.py')

// 运行Python文件并传递参数
runPython('run', 'script.py', { 
  args: ['arg1', 'arg2'], 
  returnDetailed: true 
})

// 检查Python环境
runPython('check')

// 运行Python代码字符串
runPython('code', 'print("Hello from Python!")')

// 查看帮助
runPython()
\`\`\`

功能说明：
- 直接运行现有的Python文件
- 支持向Python脚本传递命令行参数
- 在Python文件所在目录执行（保持相对路径正确）
- 同时支持代码字符串执行（通过临时文件）
- 详细的执行信息和错误处理
- 自动检查Python环境可用性

注意事项：
- 需要系统已安装Python并添加到PATH
- 运行Python文件时，会在文件所在目录执行
- 可以通过args数组传递命令行参数
- 代码字符串执行会自动创建和清理临时文件
  `,
  entry: pythonEntry
};