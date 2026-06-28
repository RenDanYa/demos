async function outgoingLinks(limit) {
  const file = this.currentFile;
  const metadata = app.metadataCache.getFileCache(file);

  if (!metadata || !metadata.links) {
    return `<div>该文件没有出链</div>`;
  }

  const frontmatterLinks = (metadata.frontmatterLinks || []).map(link => link.link);
  const links = metadata.links.map((link) => link.link) || []
  console.log("links", {
    frontmatterLinks,
    links
  })
  const uniqueLinks = [...new Set([...frontmatterLinks, ...links])]; // 去重
  console.log('uniqueLinks', uniqueLinks)
  const res = limit ? uniqueLinks.slice(0, limit) : uniqueLinks.slice(0, 20);
  console.log("res", res)
  const list = res.map((l) => {
    const path = app.metadataCache.getFirstLinkpathDest(l, "")?.path || l
    return `<li>
    <a href="${path}" data-href="${path}" class="internal-link" rel="noopener" target="_blank">${l}</a>
    </li>`;
  });

  return `<div>总计 ${uniqueLinks.length} 条</div><br/><ol>${list.join("")}</ol>`;
}

exports.default = {
  name: "outgoingLinks",
  description: `获取当前文档的出链接，默认只展示 20 条，可以通过参数调整
    
\`\`\`js
outgoingLinks()
\`\`\`

\`\`\`js
// 显示 10 条出链接
outgoingLinks(10)
\`\`\`
  `,

  entry: outgoingLinks,
};