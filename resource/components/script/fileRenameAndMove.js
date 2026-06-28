// 文件名: file-rename.js
// 放在 Templater 的 scripts 文件夹中

module.exports = async function(tp) {
    const app = tp.config.app;
    const activeFile = app.workspace.getActiveFile();
    
    if (!activeFile) {
        new Notice("没有活动的文件");
        return;
    }
    
    const newName = await tp.system.prompt("新文件名", activeFile.basename);
    
    if (newName) {
        const newPath = activeFile.path.replace(activeFile.name, newName + '.md');
        await app.vault.rename(activeFile, newPath);
        new Notice(`✅ 文件已重命名为: ${newName}.md`);
    }
};