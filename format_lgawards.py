import argparse
import re
import yaml

def parse_awards(input_text):
    """解析输入文本，提取年份、比赛名称和奖项"""
    awards = []
    lines = input_text.strip().split('\n')
    
    # 状态变量
    current_year = None
    current_contest = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 匹配年份行，例如: [2019] CSP-J二等奖
        year_match = re.match(r'\[(\d{4})\]\s*(.*)', line)
        if year_match:
            year = year_match.group(1)
            rest = year_match.group(2).strip()
            
            # 检查是否在同一行包含奖项
            award_match = re.search(r'(一等奖|二等奖|三等奖|金牌|银牌|铜牌)$', rest)
            if award_match:
                contest = rest[:award_match.start()].strip()
                award = award_match.group(0)
                awards.append((year, contest, award))
                current_year = None
                current_contest = None
            else:
                current_year = year
                current_contest = rest
        elif current_year and current_contest:
            # 处理奖项在下一行的情况
            award_match = re.match(r'(一等奖|二等奖|三等奖|金牌|银牌|铜牌)$', line)
            if award_match:
                awards.append((current_year, current_contest, award_match.group(0)))
                current_year = None
                current_contest = None
    
    return awards

def standardize_contest_name(contest):
    print("!!",contest,"!!")
    """标准化比赛名称"""
    # 映射表
    contest_map = {
        'CSP-J': 'CSP入门',
        'CSP-S': 'CSP提高',
        'NOIP普及组': 'NOIP普及',
        'NOIP提高组': 'NOIP提高',
        'NOI冬令营': 'WC',
        'NOI 冬令营': 'WC',
        'NOI夏令营': 'NOID类',
        'NOI 夏令营': 'NOID类',
        'APIO': 'APIO',
        'CTSC': 'CTSC',
        'NOI': 'NOI',
        'NOIP': 'NOIP',
        'NOIP 提高组': 'NOIP提高',
        'NOIP 普及组': 'NOIP普及',
    }
    
    # 尝试匹配映射表
    for key, value in contest_map.items():
        if key==contest:
            return value
    
    # 如果没有匹配到，返回原始名称
    return contest

def format_conditions(awards):
    """格式化条件为YAML结构"""
    conditions = []
    for year, contest, award in awards:
        standardized_contest = standardize_contest_name(contest)
        
        conditions.append({
            'year': int(year),
            'contest_type': standardized_contest,
            'award': award
        })
    
    return {'conditions': conditions}

def main():
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='将洛谷奖项认证格式化为conditions.yaml格式')
    parser.add_argument('-i', '--input', required=True, help='输入文件路径')
    parser.add_argument('-o', '--output', required=True, help='输出文件路径')
    args = parser.parse_args()
    
    # 读取输入文件
    with open(args.input, 'r', encoding='utf-8') as f:
        input_text = f.read()
    
    # 解析奖项
    awards = parse_awards(input_text)
    
    # 格式化为YAML
    conditions = format_conditions(awards)
    
    # 写入输出文件
    with open(args.output, 'w', encoding='utf-8') as f:
        yaml.dump(conditions, f, allow_unicode=True, sort_keys=False)
    
    print(f"已成功转换 {len(awards)} 个奖项条件到 {args.output}")

if __name__ == '__main__':
    main()