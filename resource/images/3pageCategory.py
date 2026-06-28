import os
import re
import yaml
from pathlib import Path

def add_page_category(md_folder):
    """
    读取文件夹下的所有md文件，添加页数档位信息
    """
    md_folder = Path(md_folder)
    
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
                data = yaml.safe_load(yaml_content)
                
                # 获取totalPage字段
                total_page = data.get('totalPage')
                
                if total_page is not None:
                    # 确保totalPage是数字
                    if isinstance(total_page, str):
                        try:
                            total_page = int(total_page)
                        except ValueError:
                            print(f"警告: {md_file.name} 的 totalPage 不是有效数字: {total_page}")
                            continue
                    
                    # 根据页数确定档位
                    if total_page < 200:
                        page_category = "200以下"
                    elif 200 <= total_page < 300:
                        page_category = "200-300"
                    elif 300 <= total_page < 400:
                        page_category = "300-400"
                    elif 400 <= total_page < 500:
                        page_category = "400-500"
                    else:
                        page_category = "500以上"
                    
                    # 添加档位信息
                    data['pageCategory'] = page_category
                    
                    # 重新生成YAML内容
                    new_yaml = yaml.dump(data, allow_unicode=True, sort_keys=False)
                    
                    # 替换原YAML内容
                    new_content = re.sub(
                        yaml_pattern, 
                        f'---\n{new_yaml}---\n', 
                        content, 
                        count=1, 
                        flags=re.DOTALL
                    )
                    
                    # 写回文件
                    with open(md_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    print(f"  成功添加档位: {page_category}")
                else:
                    print(f"  跳过: {md_file.name} 没有 totalPage 字段")
                    
            except yaml.YAMLError as e:
                print(f"  错误: 解析YAML失败 - {e}")
        else:
            print(f"  跳过: {md_file.name} 没有YAML front matter")

def main():
    # 指定包含md文件的文件夹路径
    folder_path = input("请输入包含md文件的文件夹路径: ").strip()
    
    if not os.path.exists(folder_path):
        print("文件夹不存在!")
        return
    
    print("开始处理文件...")
    add_page_category(folder_path)
    print("处理完成!")

if __name__ == "__main__":
    main()