async function embeds(limit) {
  const file = this.currentFile;
  const cache = app.metadataCache.getFileCache(file);
  if (!cache) {
    return `<div>无</div>`;
  }
  const embeds = cache.embeds || [];
  const res = embeds.map((r) => r.link);
  const links = limit ? res.slice(0, limit) : res.slice(0, 20);
  const list = links.map((l) => {
    return `<li>
    <a href="${l}" data-href="${l}" class="internal-link" rel="noopener" target="_blank">${l}</a>
    </li>`;
  });
  return `<div>总计 ${res.length} 条</div><br/><ol>${list.join("")}</ol>`;
}

exports.default = {
  name: "embeds",
  description: `获取当前文档的嵌入出链，默认只展示 20 条，可以通过参数调整
    
\`\`\`js
embeds()
\`\`\`

\`\`\`js
// 显示 10 条嵌入链接
embeds(10)
\`\`\`

    `,
  entry: embeds,
};
