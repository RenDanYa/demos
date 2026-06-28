// file-manager-independent.js
module.exports = async function(tp) {
    const app = tp.config.app;
    
    try {
        // 获取所有 Markdown 文件
        const allFiles = app.vault.getMarkdownFiles();
        
        if (allFiles.length === 0) {
            new Notice("仓库中没有 Markdown 文件");
            return;
        }
        
        // 创建文件选择列表
        const fileOptions = allFiles.map(file => ({
            name: `${file.path} (${file.basename})`,
            value: file
        }));
        
        // 选择要操作的文件
        const selectedFile = await tp.system.suggester(
            fileOptions.map(f => f.name),
            fileOptions.map(f => f.value),
            false,
            "选择要操作的文件:"
        );
        
        if (!selectedFile) {
            new Notice("操作已取消");
            return;
        }
        
        // 选择操作类型
        const operation = await tp.system.suggester(
            ["重命名文件", "移动文件", "重命名并移动"],
            ["rename", "move", "both"],
            false,
            "选择操作类型:"
        );
        
        if (!operation) return;
        
        let newName = selectedFile.basename;
        let newPath = selectedFile.path;
        
        // 处理重命名
        if (operation === "rename" || operation === "both") {
            newName = await tp.system.prompt(
                "输入新文件名 (不带 .md 扩展名):",
                selectedFile.basename
            );
            
            if (!newName) return;
            
            // 更新路径中的文件名部分
            const pathParts = newPath.split('/');
            pathParts[pathParts.length - 1] = newName + '.md';
            newPath = pathParts.join('/');
        }
        
        // 处理移动
        if (operation === "move" || operation === "both") {
            // 获取所有文件夹
            const allFolders = app.vault.getAllLoadedFiles()
                .filter(file => file.children) // 只有文件夹有 children 属性
                .map(folder => folder.path);
            
            // 添加当前文件夹和根目录选项
            const currentFolder = selectedFile.parent ? selectedFile.parent.path : "/";
            const folderOptions = ["/ (根目录)", currentFolder + " (当前文件夹)", ...allFolders];
            
            const targetFolder = await tp.system.suggester(
                folderOptions,
                folderOptions,
                false,
                "选择目标文件夹:"
            );
            
            if (targetFolder) {
                const fileName = newPath.split('/').pop();
                
                if (targetFolder === "/ (根目录)") {
                    newPath = fileName;
                } else if (targetFolder.endsWith(" (当前文件夹)")) {
                    // 保持当前文件夹不变
                } else {
                    newPath = `${targetFolder}/${fileName}`;
                }
            }
        }
        
        // 确认操作
        if (newPath !== selectedFile.path) {
            const confirm = await tp.system.prompt(
                `确认执行以下操作:\n\n从: ${selectedFile.path}\n到: ${newPath}\n\n输入 "YES" 确认:`,
                ""
            );
            
            if (confirm && confirm.toUpperCase() === "YES") {
                try {
                    // 确保目标目录存在
                    const targetDir = newPath.substring(0, newPath.lastIndexOf('/'));
                    if (targetDir && !app.vault.getAbstractFileByPath(targetDir)) {
                        await app.vault.createFolder(targetDir);
                    }
                    
                    await app.vault.rename(selectedFile, newPath);
                    new Notice(`✅ 文件操作成功: ${newPath}`);
                } catch (error) {
                    new Notice(`❌ 操作失败: ${error.message}`);
                }
            } else {
                new Notice("操作已取消");
            }
        } else {
            new Notice("没有进行任何更改");
        }
        
    } catch (error) {
        new Notice(`❌ 脚本执行错误: ${error.message}`);
        console.error("Templater 脚本错误:", error);
    }
};