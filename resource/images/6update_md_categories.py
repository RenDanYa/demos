import os
import pandas as pd
import frontmatter
import yaml
from pathlib import Path

def update_md_files_from_excel(excel_file, md_folder):
    """
    根据Excel文件中的数据更新Markdown文件的属性
    
    Args:
        excel_file: Excel文件路径
        md_folder: Markdown文件所在文件夹路径
    """
    # 读取Excel文件
    try:
        # 使用中文列名读取Excel
        df = pd.read_excel(excel_file)
        print(f"成功读取Excel文件，共{len(df)}条记录")
        print(f"列名: {df.columns.tolist()}")  # 打印列名以便调试
    except Exception as e:
        print(f"读取Excel文件失败: {e}")
        return
    
    # 检查列名并创建映射字典
    title_to_category = {}
    
    # 检查列名，尝试不同的可能列名
    if 'title' in df.columns and 'category' in df.columns:
        title_col = 'title'
        category_col = 'category'
    elif '书名' in df.columns and '类别' in df.columns:
        title_col = '书名'
        category_col = '类别'
    elif 'A' in df.columns and 'B' in df.columns:  # 根据你提供的Excel内容，列名可能是A和B
        title_col = 'A'
        category_col = 'B'
    else:
        # 如果没有匹配的列名，使用第一列和第二列
        print("未找到标准列名，使用第一列和第二列")
        title_col = df.columns[0]
        category_col = df.columns[1]
    
    print(f"使用列映射: {title_col} -> {category_col}")
    
    for _, row in df.iterrows():
        title = str(row[title_col]).strip()
        category = str(row[category_col]).strip()
        title_to_category[title] = category
        print(f"映射: {title} -> {category}")
    
    # 遍历Markdown文件
    md_files = list(Path(md_folder).glob("*.md"))
    print(f"\n找到{len(md_files)}个Markdown文件")
    
    updated_count = 0
    for md_file in md_files:
        try:
            # 读取Markdown文件内容
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析front matter
            post = frontmatter.loads(content)
            
            # 获取文件名（不含扩展名）
            file_name = md_file.stem
            print(f"\n处理文件: {file_name}")
            
            # 查找对应的类别
            if file_name in title_to_category:
                new_category = title_to_category[file_name]
                old_category = post.get('category', '未设置')
                
                # 更新category属性
                post['category'] = new_category
                
                # 将更新后的内容写回文件
                updated_content = frontmatter.dumps(post)
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                
                print(f"  更新成功: {old_category} -> {new_category}")
                updated_count += 1
            else:
                print(f"  未找到对应的类别映射")
                
        except Exception as e:
            print(f"处理文件 {md_file} 时出错: {e}")
    
    print(f"\n完成！成功更新了 {updated_count} 个文件")

def main():
    # 文件路径配置
    excel_file = "类别.xlsx"  # Excel文件路径
    md_folder = "D:/obsidian/demo/05_long_project/书/豆瓣/"  # Markdown文件所在文件夹路径
    
    # 检查文件是否存在
    if not os.path.exists(excel_file):
        print(f"Excel文件不存在: {excel_file}")
        return
    
    if not os.path.exists(md_folder):
        print(f"Markdown文件夹不存在: {md_folder}")
        return
    
    # 执行更新
    update_md_files_from_excel(excel_file, md_folder)

if __name__ == "__main__":
    main()