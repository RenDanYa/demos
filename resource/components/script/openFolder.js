async function openFolder(folder) {
  if (!folder) {
    new obsidian.Notice("请指定目录或文件夹");
    return;
  }

  const f = app.vault.getAbstractFileByPath(folder);
  if (f instanceof obsidian.TFolder || f instanceof obsidian.TFile) {
    const fileExplorer =
      // @ts-ignore
      app.internalPlugins.plugins["file-explorer"].instance;
    fileExplorer.revealInFolder(f);
  }
}

exports.default = {
  name: "openFolder",
  description: `在文件列表中高亮定位指定的文件或文件夹
    
\`\`\`js
openFolder("journal/2024/")
\`\`\`

\`\`\`js
openFolder("journal/2024/2024-01-01.md")
\`\`\`

    `,
  entry: openFolder,
};
