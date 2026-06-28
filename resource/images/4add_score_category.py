import os
import re
import yaml
from pathlib import Path

def add_score_category(md_folder):
    """
    读取文件夹下的所有md文件，添加评分档位信息
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
                
                # 获取score字段
                score = data.get('score')
                
                if score is not None:
                    # 确保score是数字
                    if isinstance(score, str):
                        try:
                            score = float(score)
                        except ValueError:
                            print(f"警告: {md_file.name} 的 score 不是有效数字: {score}")
                            continue
                    else:
                        score = float(score)
                    
                    # 根据评分确定档位
                    if score < 6:
                        score_category = "6以下"
                    elif 6 <= score < 6.5:
                        score_category = "6-6.5"
                    elif 6.5 <= score < 7:
                        score_category = "6.5-7"
                    elif 7 <= score < 7.5:
                        score_category = "7-7.5"
                    elif 7.5 <= score < 8:
                        score_category = "7.5-8"
                    elif 8 <= score < 8.5:
                        score_category = "8-8.5"
                    elif 8.5 <= score < 9:
                        score_category = "8.5-9"
                    else:  # score >= 9
                        score_category = "9以上"
                    
                    # 添加档位信息
                    data['scoreCategory'] = score_category
                    
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
                    
                    print(f"  成功添加评分档位: {score_category}")
                else:
                    print(f"  跳过: {md_file.name} 没有 score 字段")
                    
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
    add_score_category(folder_path)
    print("处理完成!")

if __name__ == "__main__":
    main()