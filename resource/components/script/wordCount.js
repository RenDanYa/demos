function countCharacters(str) {
  // 去除所有标点符号
  const cleanStr = str.replace(/[^\p{L}\s]/gu, "");
  // 将字符串分割成单词和非英文字符
  const words = cleanStr.match(/\b[a-zA-Z]+\b|\S/gu) || [];
  // 返回数组长度，即字符数量
  return words.length;
}

async function countWordCharactersFromFile() {
  const { currentFile } = this
  const file = currentFile;
  if (file.extension !== "md") {
    return "仅支持 Markdown 文件统计";
  }
  const fileContent = await app.vault.cachedRead(file);
  const contentWithoutFrontmatter =
    (fileContent || "").replace(/^---[\s\S]*?---\s*/, "") || "";
  return countCharacters(contentWithoutFrontmatter);
}

exports.default = {
    name: 'countWordCharactersFromFile',
    description: `Count word characters
    
\`\`\`js
countWordCharactersFromFile()
\`\`\`

    `,
    entry: countWordCharactersFromFile
}