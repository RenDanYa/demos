import os
import re
import yaml
import pandas as pd
from pathlib import Path

def extract_title_category_to_excel(md_folder, output_file):
    """
    读取文件夹下的所有md文件，提取title和category字段，保存到Excel中
    """
    md_folder = Path(md_folder)
    
    # 存储提取的数据
    data = []
    
    # 遍历文件夹中的所有md文件
    for md_file in md_folder.glob("*.md"):
        print(f"处理文件: {md_file.name}")
        
        # 读取文件内容
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则表达式匹配YAML front matter
        yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.search(yaml_pattern, content, re.DOTALL)
        
        if match:
            yaml_content = match.group(1)
            
            try:
                # 解析YAML
                front_matter = yaml.safe_load(yaml_content)
                
                # 提取title和category
                title = front_matter.get('title', '')
                
                # 处理category字段，可能是列表或字符串
                category = front_matter.get('category', '')
                if isinstance(category, list):
                    category = ', '.join(category)
                
                # 添加到数据列表
                data.append({
                    'title': title,
                    'category': category,
                    'filename': md_file.name
                })
                
                print(f"  提取成功: {title}")
                    
            except yaml.YAMLError as e:
                print(f"  错误: 解析YAML失败 - {e}")
        else:
            print(f"  跳过: {md_file.name} 没有YAML front matter")
    
    # 如果没有提取到数据，则返回
    if not data:
        print("没有提取到任何数据!")
        return
    
    # 创建DataFrame并保存为Excel
    df = pd.DataFrame(data)
    
    # 确保输出目录存在
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存为Excel文件
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"\n数据已保存到: {output_file}")
    print(f"共处理 {len(data)} 条记录")

def main():
    # 指定包含md文件的文件夹路径
    folder_path = input("请输入包含md文件的文件夹路径: ").strip()
    
    if not os.path.exists(folder_path):
        print("文件夹不存在!")
        return
    
    # 指定输出Excel文件路径
    output_file = input("请输入输出Excel文件路径 (例如: output.xlsx): ").strip()
    if not output_file:
        output_file = "output.xlsx"
    
    print("开始处理文件...")
    extract_title_category_to_excel(folder_path, output_file)
    print("处理完成!")

if __name__ == "__main__":
    main()