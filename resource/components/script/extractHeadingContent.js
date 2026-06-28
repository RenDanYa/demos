async function extractHeadingContent(heading, options) {
  if (!heading || heading === "") {
    return "请输入想提取的标题字段，比如： ## 总结";
  }

  // options
  const hideHeading = options?.hideHeading === true;
  const includeSubHeadingContent = options?.includeSubHeadingContent === true;

  const { currentFile } = this;
  const file = currentFile;
  const cache = app.metadataCache.getFileCache(file);
  const headings = cache?.headings || [];
  const expectedHeading = heading || "";

  let match = -1;
  for (let i = 0; i < headings.length; i++) {
    const h = headings[i];
    const sharps = "#".repeat(h.level);
    const head = `${sharps} ${h.heading}`;
    if (head === expectedHeading) {
      match = i;
      break;
    }
  }
  if (match === -1) {
    return "";
  }

  const fileContent = await app.vault.cachedRead(file);
  const fileContentLines = fileContent.split("\n");
  if (match >= 0) {
    const matchLine = headings[match].position.start.line;
    const start = hideHeading ? matchLine + 1 : matchLine;
    const nextHeading = getEndPosition(
      includeSubHeadingContent,
      headings,
      match
    );
    let res;
    if (nextHeading) {
      const nextLine = nextHeading.position.start.line;
      // get line from match line to next heading line
      const headingContent = fileContentLines.slice(start, nextLine).join("\n");
      res = headingContent;
    } else {
      // get line from match line
      const headingContent = fileContentLines.splice(start).join("\n");
      res = headingContent;
    }
    return res;
  } else {
    return "";
  }
}

function getEndPosition(includeSubHeadingContent, headings, match) {
  const nextLine = match + 1;
  if (includeSubHeadingContent) {
    for (let i = nextLine; i < headings.length; i++) {
      const h = headings[i];
      if (h.level <= headings[match].level) {
        return h;
      }
    }
  }
  return nextLine >= headings.length ? null : headings[nextLine];
}

exports.default = {
  name: "extractHeadingContent",
  description: `提取指定标题下的文本内容

  使用方法

  \`\`\`js
  extractHeadingContent('## 你的标题')
  \`\`\`
  
  不包含标题
  \`\`\`js
  extractHeadingContent('## 你的标题', { hideHeading: true })
  \`\`\`

  不包含标题同时展示指定标题下的全部内容

  \`\`\`js
  extractHeadingContent('# 元数据', { hideHeading: true, includeSubHeadingContent: true })
  \`\`\`

      `,
  entry: extractHeadingContent,
};
