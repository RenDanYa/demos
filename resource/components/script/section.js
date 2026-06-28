async function section(tag) {
  const file = this.currentFile;
  if (!tag || tag === "" || typeof tag !== "string") {
    new obsidian.Notice(
      "section: tag is required and should be a string"
    );
    return "";
  }
  if (!file || file.extension !== "md") {
    return "";
  }

  const content = await app.vault.cachedRead(file, tag);
  const res = parseTaggedSection(content, tag);
  return res.join("\n\n");
}

function parseTaggedSection(text, tag) {
  const content = text.replace(/^---[\s\S]*?---\s?/, "");
  const paragraphs = content.split(/\n\n+/) || [];
  const matchingParagraphs = paragraphs.filter((p) => p.includes(tag));
  return matchingParagraphs;
}

exports.default = {
  name: "section",
  description: `

- 使用方式

包含指定标签的段落

\`\`\`js
section("#锻炼")
\`\`\`

包含指定文本的段落

\`\`\`js
section("天气: 晴")
\`\`\`

  `,
  entry: section,
};
