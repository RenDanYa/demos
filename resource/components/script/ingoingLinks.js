async function ingoingLinks(limit) {
  const file = this.currentFile;
  const resolvedLinks = app.metadataCache.resolvedLinks;
  const ingoingLinks = new Map();
  Object.entries(resolvedLinks).forEach((entry) => {
    const [key, value] = entry;
    const links = Object.keys(value);
    links.forEach((link) => {
      const list = ingoingLinks.get(link) || [];
      list.push(key);
      ingoingLinks.set(link, list);
    });
  });

  const res = ingoingLinks.get(file.path) || [];
  const links = limit ? res.slice(0, limit) : res.slice(0, 20);
  const list = links.map((l) => {
    return `<li>
    <a href="${l}" data-href="${l}" class="internal-link" rel="noopener" target="_blank">${l}</a>
    </li>`;
  });
  return `<div>总计 ${res.length} 条</div><br/><ol>${list.join("")}</ol>`;
}

exports.default = {
  name: "ingoingLinks",
  description: `获取当前文档的入链接，默认只展示 20 条，可以通过参数调整
    
\`\`\`js
ingoingLinks()
\`\`\`

\`\`\`js
// 显示 10 条入链接
ingoingLinks(10)
\`\`\`

    `,
  entry: ingoingLinks,
};
