async function inlineProperty(propertyName) {
  const file = this.currentFile;
  if (
    !propertyName ||
    propertyName === "" ||
    typeof propertyName !== "string"
  ) {
    new obsidian.Notice(
      "inlineProperty: propertyName is required and should be a string"
    );
    return "";
  }
  if (!file || file.extension !== "md") {
    return "";
  }

  const content = await app.vault.cachedRead(file);
  const res = parseInlineFields(content);
  const result = res.find((item) => item.property === propertyName);
  if (result) {
    return result.value;
  }
  return "";
}

function parseInlineFields(text) {
  const results = [];

  const lines = text.split(/\r?\n/);
  // match text separated by `::`

  // const regex = /(\w+)\s*::\s*([^#\n]+)/g;
  const regex = /([\w\u4e00-\u9fff]+)\s*::\s*([^#\n]+)/g;

  for (let line of lines) {
    // if surrounded by `[]` or `()`, remove start and end
    if (
      line.startsWith("- ") ||
      line.startsWith("* ") ||
      line.startsWith("+ ")
    ) {
      line = line.slice(2);
    }

    if (line.startsWith("[") && line.endsWith("]")) {
      line = line.slice(1, -1);
    } else if (line.startsWith("(") && line.endsWith(")")) {
      line = line.slice(1, -1);
    }
    let match;
    while ((match = regex.exec(line)) !== null) {
      const property = match[1].trim();
      const value = match[2].trim();
      
      const exist = results.find((item) => item.property === property);
      if (exist) {
        exist.value = `${exist.value}, ${value}`;
      } else {
        results.push({ property, value });
      }
    }
  }

  return results;
}

exports.default = {
  name: "inlineProperty",
  description: `
提取当前文件中的内联属性值，例如 \`age::18\`，提取出 \`18\`。（内联属性是由 dataview 插件定义的属性格式）

- 使用方式

\`\`\`js
inlineProperty("age")
\`\`\`
  `,
  entry: inlineProperty,
};
