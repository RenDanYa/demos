import re
import pandas as pd
from urllib.parse import unquote
from pathlib import Path
import logging
from typing import List, Dict, Tuple, Optional
import json

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_zli_number(url: str) -> Optional[int]:
    """
    从URL中提取Z-Li_后面的阿拉伯数字
    例如: Z-Li_190_ => 190, Z-Li_02_ => 2, Z-Li_12_ => 12
    
    返回:
        如果找到数字则返回整数，否则返回None
    """
    # 查找Z-Li_后面跟着数字的模式
    pattern = r'Z-Li_(\d+)[_.]'
    match = re.search(pattern, url)
    
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            logger.warning(f"无法转换数字: {match.group(1)} in URL: {url}")
            return None
    
    # 如果没找到Z-Li_模式，尝试其他常见的数字模式
    # 查找_Li_后面的数字
    pattern2 = r'_Li_(\d+)[_.]'
    match2 = re.search(pattern2, url)
    if match2:
        try:
            return int(match2.group(1))
        except ValueError:
            logger.warning(f"无法转换数字: {match2.group(1)} in URL: {url}")
            return None
    
    # 查找文件末尾的数字，如_190.pdf
    pattern3 = r'_(\d{2,3})\.(pdf|PDF)'
    match3 = re.search(pattern3, url)
    if match3:
        try:
            return int(match3.group(1))
        except ValueError:
            logger.warning(f"无法转换数字: {match3.group(1)} in URL: {url}")
            return None
    
    return None

def parse_markdown_by_headers(md_content: str) -> List[Dict]:
    """
    解析Markdown文档，提取所有一级标题及其内容
    
    返回:
        包含章节信息的字典列表
    """
    sections = []
    lines = md_content.split('\n')
    
    current_section = None
    
    for i, line in enumerate(lines):
        # 检查是否是一级标题（# 开头，后面跟空格）
        if re.match(r'^#\s+.+$', line.strip()):
            # 保存上一个章节（如果有）
            if current_section is not None:
                sections.append(current_section)
            
            # 开始新章节
            current_section = {
                'header': line.strip(),
                'content': [],
                'lines': [],
                'urls': [],
                'zli_numbers': [],
                'min_zli_number': None,
                'original_position': len(sections)  # 记录原始位置
            }
        elif current_section is not None:
            current_section['content'].append(line)
            current_section['lines'].append(line)
    
    # 添加最后一个章节
    if current_section is not None:
        sections.append(current_section)
    
    return sections

def extract_urls_from_section(section: Dict) -> None:
    """
    从章节内容中提取所有URL，并找出Z-Li_数字
    """
    content_str = '\n'.join(section['content'])
    
    # 提取所有URL
    url_patterns = [
        r'https?://[^\s<>"\'()]+',  # 普通URL
        r'\(https?://[^\s<>"\'()]+\)',  # 括号内的URL
        r'\[.*?\]\((https?://[^\s<>"\'()]+)\)',  # Markdown链接
    ]
    
    raw_urls = []
    for pattern in url_patterns:
        matches = re.findall(pattern, content_str)
        for match in matches:
            # 处理括号内的URL
            if match.startswith('(') and match.endswith(')'):
                match = match[1:-1]
            raw_urls.append(match)
    
    # 去重并解码
    seen = set()
    decoded_urls = []
    for url in raw_urls:
        if url not in seen:
            seen.add(url)
            try:
                decoded_url = unquote(url)
                decoded_urls.append(decoded_url)
            except Exception as e:
                logger.warning(f"解码URL失败: {url}, 错误: {e}")
                decoded_urls.append(url)
    
    # 提取Z-Li数字并排序
    zli_numbers = []
    valid_urls = []
    
    for url in decoded_urls:
        zli_num = extract_zli_number(url)
        if zli_num is not None:
            zli_numbers.append(zli_num)
            valid_urls.append(url)
    
    # 按Z-Li数字排序URL
    if valid_urls:
        sorted_pairs = sorted(zip(zli_numbers, valid_urls), key=lambda x: x[0])
        sorted_zli_numbers, sorted_urls = zip(*sorted_pairs)
        
        section['urls'] = list(sorted_urls)
        section['zli_numbers'] = list(sorted_zli_numbers)
        section['min_zli_number'] = min(zli_numbers) if zli_numbers else None
    else:
        section['urls'] = []
        section['zli_numbers'] = []
        section['min_zli_number'] = None

def sort_sections_by_zli_number(sections: List[Dict]) -> List[Dict]:
    """
    根据Z-Li数字对章节进行排序
    
    排序规则:
    1. 有Z-Li数字的章节按最小Z-Li数字升序排列
    2. 没有Z-Li数字的章节保持原始相对顺序，放在有数字的章节后面
    """
    # 分离有数字和无数字的章节
    sections_with_numbers = []
    sections_without_numbers = []
    
    for section in sections:
        if section['min_zli_number'] is not None:
            sections_with_numbers.append(section)
        else:
            sections_without_numbers.append(section)
    
    # 按最小Z-Li数字排序
    sections_with_numbers.sort(key=lambda x: x['min_zli_number'])
    
    # 无数字章节保持原始顺序
    sections_without_numbers.sort(key=lambda x: x['original_position'])
    
    # 合并结果：有数字的在前，无数字的在后
    return sections_with_numbers + sections_without_numbers

def rebuild_markdown(sections: List[Dict]) -> str:
    """
    根据排序后的章节重建Markdown文档
    """
    markdown_lines = []
    
    for i, section in enumerate(sections):
        # 添加标题
        markdown_lines.append(section['header'])
        
        # 添加内容
        markdown_lines.extend(section['lines'])
        
        # 章节之间添加空行分隔（除非是最后一个章节）
        if i < len(sections) - 1:
            markdown_lines.append('')
    
    return '\n'.join(markdown_lines)

def process_markdown_file(md_file_path: str, output_file_path: str = None) -> Tuple[str, List[Dict]]:
    """
    处理Markdown文件：按Z-Li数字排序章节
    
    参数:
        md_file_path: Markdown文件路径
        output_file_path: 输出文件路径（可选）
    
    返回:
        Tuple[排序后的文档内容, 排序后的章节信息]
    """
    # 读取Markdown文件
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # 解析文档
    sections = parse_markdown_by_headers(md_content)
    
    logger.info(f"找到 {len(sections)} 个一级标题")
    
    # 提取每个章节的URL和Z-Li数字
    for section in sections:
        extract_urls_from_section(section)
    
    # 按Z-Li数字排序章节
    sorted_sections = sort_sections_by_zli_number(sections)
    
    # 重建文档
    sorted_content = rebuild_markdown(sorted_sections)
    
    # 保存输出文件
    if output_file_path:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(sorted_content)
        logger.info(f"已保存排序后的文档到: {output_file_path}")
    
    return sorted_content, sorted_sections

def generate_sorting_report(sections: List[Dict], report_path: str = None) -> pd.DataFrame:
    """
    生成排序报告
    """
    report_data = []
    
    for i, section in enumerate(sections, 1):
        header_text = section['header'].replace('# ', '').strip()
        min_zli_num = section['min_zli_number']
        url_count = len(section['urls'])
        
        # 获取前几个URL作为示例
        sample_urls = section['urls'][:3] if section['urls'] else []
        sample_str = "; ".join([url.split('/')[-1][:30] + "..." for url in sample_urls])
        
        report_data.append({
            '排序序号': i,
            '原始序号': section['original_position'] + 1,
            '标题': header_text[:50] + "..." if len(header_text) > 50 else header_text,
            '最小Z-Li数字': min_zli_num if min_zli_num is not None else "无",
            'URL数量': url_count,
            'Z-Li数字列表': str(section['zli_numbers']) if section['zli_numbers'] else "无",
            'URL示例': sample_str if sample_str else "无"
        })
    
    df = pd.DataFrame(report_data)
    
    if report_path:
        if report_path.endswith('.xlsx'):
            df.to_excel(report_path, index=False)
            logger.info(f"已保存报告到Excel: {report_path}")
        elif report_path.endswith('.csv'):
            df.to_csv(report_path, index=False, encoding='utf-8-sig')
            logger.info(f"已保存报告到CSV: {report_path}")
    
    return df

def export_url_list(sections: List[Dict], export_path: str = None) -> pd.DataFrame:
    """
    导出所有URL的详细列表
    """
    url_data = []
    
    for section_idx, section in enumerate(sections, 1):
        header_text = section['header'].replace('# ', '').strip()
        
        for url_idx, (url, zli_num) in enumerate(zip(section['urls'], section['zli_numbers']), 1):
            url_data.append({
                '章节序号': section_idx,
                '章节标题': header_text[:30] + "..." if len(header_text) > 30 else header_text,
                'URL序号': url_idx,
                'Z-Li数字': zli_num,
                'URL': url,
                '文件名': url.split('/')[-1] if '/' in url else url
            })
    
    df = pd.DataFrame(url_data)
    
    if export_path:
        if export_path.endswith('.xlsx'):
            df.to_excel(export_path, index=False)
            logger.info(f"已导出URL列表到Excel: {export_path}")
        elif export_path.endswith('.csv'):
            df.to_csv(export_path, index=False, encoding='utf-8-sig')
            logger.info(f"已导出URL列表到CSV: {export_path}")
    
    return df

def main():
    """主函数"""
    
    print("=" * 70)
    print("Markdown文档章节排序工具 - 按Z-Li数字排序")
    print("=" * 70)
    
    # 配置文件路径
    md_file_path = input("请输入Markdown文件路径（默认: 未命名 7.md）: ").strip()
    if not md_file_path:
        md_file_path = "未命名 7.md"
    
    if not Path(md_file_path).exists():
        print(f"错误: 文件 '{md_file_path}' 不存在")
        return
    
    # 生成输出文件名
    stem = Path(md_file_path).stem
    default_output = f"sorted_{stem}.md"
    default_report = f"sorting_report_{stem}.xlsx"
    default_url_list = f"url_list_{stem}.xlsx"
    
    # 输出文件路径
    output_md_path = input(f"请输入输出Markdown文件路径（默认: {default_output}）: ").strip()
    if not output_md_path:
        output_md_path = default_output
    
    print("\n" + "=" * 70)
    print("开始处理...")
    print("=" * 70)
    
    try:
        # 处理文档
        sorted_content, sorted_sections = process_markdown_file(md_file_path, output_md_path)
        
        print(f"\n✅ 成功处理 {len(sorted_sections)} 个章节")
        
        # 显示排序摘要
        print("\n📊 排序结果摘要:")
        print("-" * 50)
        
        sections_with_numbers = [s for s in sorted_sections if s['min_zli_number'] is not None]
        sections_without_numbers = [s for s in sorted_sections if s['min_zli_number'] is None]
        
        print(f"有Z-Li数字的章节: {len(sections_with_numbers)} 个")
        print(f"无Z-Li数字的章节: {len(sections_without_numbers)} 个")
        
        if sections_with_numbers:
            print("\n按Z-Li数字排序的章节:")
            for i, section in enumerate(sections_with_numbers[:10], 1):  # 只显示前10个
                header = section['header'].replace('# ', '').strip()
                num = section['min_zli_number']
                print(f"  {i:2d}. Z-Li_{num:03d} - {header[:40]}...")
            
            if len(sections_with_numbers) > 10:
                print(f"  ... 还有 {len(sections_with_numbers) - 10} 个章节")
        
        # 询问是否生成报告
        print("\n" + "=" * 70)
        
        gen_report = input(f"是否生成排序报告？(y/n, 默认:y): ").strip().lower()
        if gen_report != 'n':
            report_path = input(f"请输入报告文件路径（默认: {default_report}）: ").strip()
            if not report_path:
                report_path = default_report
            df_report = generate_sorting_report(sorted_sections, report_path)
        
        gen_url_list = input(f"是否导出URL详细列表？(y/n, 默认:y): ").strip().lower()
        if gen_url_list != 'n':
            url_list_path = input(f"请输入URL列表文件路径（默认: {default_url_list}）: ").strip()
            if not url_list_path:
                url_list_path = default_url_list
            df_urls = export_url_list(sorted_sections, url_list_path)
        
        print("\n" + "=" * 70)
        print("🎉 处理完成！")
        print(f"📄 排序后的文档: {output_md_path}")
        if gen_report != 'n':
            print(f"📊 排序报告: {report_path}")
        if gen_url_list != 'n':
            print(f"🔗 URL详细列表: {url_list_path}")
        
        # 显示示例
        print("\n🔍 排序后前5个章节的Z-Li数字:")
        print("-" * 50)
        for i, section in enumerate(sorted_sections[:5], 1):
            header = section['header'].replace('# ', '').strip()[:40]
            num = section['min_zli_number']
            if num is not None:
                print(f"{i}. Z-Li_{num:03d} - {header}...")
            else:
                print(f"{i}. 无Z-Li数字 - {header}...")
        
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

def quick_process(md_file_path: str):
    """
    快速处理函数（无交互）
    """
    try:
        stem = Path(md_file_path).stem
        output_path = f"sorted_{stem}.md"
        report_path = f"sorting_report_{stem}.xlsx"
        url_list_path = f"url_list_{stem}.xlsx"
        
        sorted_content, sorted_sections = process_markdown_file(md_file_path, output_path)
        df_report = generate_sorting_report(sorted_sections, report_path)
        df_urls = export_url_list(sorted_sections, url_list_path)
        
        print(f"✅ 快速处理完成:")
        print(f"   排序文档: {output_path}")
        print(f"   排序报告: {report_path}")
        print(f"   URL列表: {url_list_path}")
        
        # 显示Z-Li数字范围
        zli_numbers = []
        for section in sorted_sections:
            zli_numbers.extend(section['zli_numbers'])
        
        if zli_numbers:
            print(f"   Z-Li数字范围: {min(zli_numbers)} - {max(zli_numbers)}")
            print(f"   共 {len(zli_numbers)} 个Z-Li数字")
        
        return sorted_content, df_report, df_urls
        
    except Exception as e:
        print(f"快速处理失败: {e}")
        return None, None, None

# 测试函数
def test_zli_extraction():
    """测试Z-Li数字提取功能"""
    test_urls = [
        "https://x-1381123255.cos.ap-beijing.myqcloud.com/搞定：无压工作的艺术时间管理%2B提升工作%2B平衡工作与生活的艺术美（共三册） (戴维·艾伦) (Z-Li_190_目录.pdf",
        "https://x-1381123255.cos.ap-beijing.myqcloud.com/搞定：无压工作的艺术时间管理%2B提升工作%2B平衡工作与生活的艺术美（共三册） (戴维·艾伦) (Z-Li_02_目录.pdf",
        "https://x-1381123255.cos.ap-beijing.myqcloud.com/搞定：无压工作的艺术时间管理%2B提升工作%2B平衡工作与生活的艺术美（共三册） (戴维·艾伦) (Z-Li_191_未知章节.pdf",
        "https://x-1381123255.cos.ap-beijing.myqcloud.com/搞定：无压工作的艺术时间管理%2B提升工作%2B平衡工作与生活的艺术美（共三册） (戴维·艾伦) (Z-Li_100_引言.pdf",
        "https://x-1381123255.cos.ap-beijing.myqcloud.com/搞定：无压工作的艺术时间管理%2B提升工作%2B平衡工作与生活的艺术美（共三册） (戴维·艾伦) (_Li_150_优先排序的难题.pdf",
        "https://example.com/file_190.pdf",
        "https://example.com/no_number_here.html"
    ]
    
    print("测试Z-Li数字提取:")
    print("-" * 50)
    
    for url in test_urls:
        decoded = unquote(url)
        zli_num = extract_zli_number(decoded)
        print(f"URL: {decoded.split('/')[-1][:40]}...")
        print(f"提取的Z-Li数字: {zli_num}")
        print()

# 示例用法
if __name__ == "__main__":
    # 方法1: 交互式运行
    main()
    
    # 方法2: 快速运行（取消注释以下代码）
    # result = quick_process("未命名 7.md")
    
    # 方法3: 测试Z-Li数字提取（取消注释以下代码）
    # test_zli_extraction()