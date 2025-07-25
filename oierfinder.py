#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import argparse
import pickle
import yaml
from datetime import datetime
from school import School
from contest import Contest
from oier import OIer
from record import Record

def load_data(data_file):
    """加载序列化数据并完整重建对象关系"""
    try:
        # 增加递归深度限制
        import sys
        sys.setrecursionlimit(10000)
        
        with open(data_file, 'rb') as f:
            data = pickle.load(f)
    except FileNotFoundError:
        print(f"错误: 数据文件 {data_file} 不存在")
        return None
    except Exception as e:
        print(f"加载数据失败: {e}")
        return None
    
    # 提取数据
    schools = data['schools']
    contests = data['contests']
    oiers = data['oiers']
    records = data['records']
    
    # === 1. 创建查找字典 ===
    school_by_id = {s.id: s for s in schools}
    contest_by_id = {c.id: c for c in contests}
    oier_by_uid = {o.uid: o for o in oiers}
    record_by_id = {r.id: r for r in records}
    
    # === 2. 重建 Record 对象的引用 ===
    for record in records:
        # 重建 OIer 引用
        if isinstance(record.oier, int):  # 如果是 UID
            record.oier = oier_by_uid.get(record.oier)
        
        # 重建 Contest 引用
        if isinstance(record.contest, int):  # 如果是 ID
            record.contest = contest_by_id.get(record.contest)
        
        # 重建 School 引用
        if isinstance(record.school, int):  # 如果是 ID
            record.school = school_by_id.get(record.school)
    
    # === 3. 重建 OIer 对象的 records 列表 ===
    for oier in oiers:
        # 检查 records 是否是 ID 列表
        if isinstance(oier.records, list) and all(isinstance(rid, int) for rid in oier.records):
            oier.records = [record_by_id[rid] for rid in oier.records if rid in record_by_id]
    
    # === 4. 重建 Contest 对象的 contestants 列表 ===
    for contest in contests:
        # 检查 contestants 是否是 ID 列表
        if isinstance(contest.contestants, list) and all(isinstance(rid, int) for rid in contest.contestants):
            contest.contestants = [record_by_id[rid] for rid in contest.contestants if rid in record_by_id]
    
    # === 5. 重建类静态变量 ===
    # 对于 School 类
    School.__all_school_list__ = schools
    School.__school_name_map__ = {}
    for school in schools:
        School.__school_name_map__[school.name] = school
        for alias in school.aliases:
            School.__school_name_map__[alias] = school
    
    # 对于 Contest 类
    Contest.__all_contests_list__ = contests
    Contest.__all_contests_map__ = {}
    for contest in contests:
        Contest.__all_contests_map__[contest.name] = contest
    
    # 对于 OIer 类
    OIer.__all_oiers_list__ = oiers
    OIer.__all_oiers_map__ = {}
    for oier in oiers:
        key = (oier.name, oier.identifier)
        OIer.__all_oiers_map__[key] = oier
    
    # 对于 Record 类
    Record.__all_records_list__ = records
    
    # 重建 Contest 中的 contestants 列表（确保双向引用）
    for contest in contests:
        # 如果 contestants 不是 Record 对象列表，则重建
        if not contest.contestants or not isinstance(contest.contestants[0], Record):
            contest.contestants = [r for r in records if r.contest and r.contest.id == contest.id]
    
    # 重建 OIer 中的 records 列表（确保双向引用）
    for oier in oiers:
        # 如果 records 不是 Record 对象列表，则重建
        if not oier.records or not isinstance(oier.records[0], Record):
            oier.records = [r for r in records if r.oier and r.oier.uid == oier.uid]
    
    return {
        'schools': schools,
        'contests': contests,
        'oiers': oiers,
        'records': records
    }

def parse_conditions(config_file):
    """解析 YAML 配置文件中的筛选条件"""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"错误: 配置文件 {config_file} 不存在")
        return None
    except yaml.YAMLError as e:
        print(f"解析 YAML 失败: {e}")
        return None
    
    # 验证配置结构
    if 'conditions' not in config:
        print("错误: 配置文件中缺少 'conditions' 部分")
        return None
    
    conditions = []
    
    for cond in config['conditions']:
        # 验证必需字段
        if 'contest_type' not in cond:
            print("错误: 条件缺少 'contest_type' 字段")
            continue
        
        # 创建条件字典
        condition = {
            'contest_type': cond['contest_type'],
            'award': cond.get('award'),
            'min_award': cond.get('min_award'),
            'year_range': cond.get('year_range', []),
            'province': cond.get('province'),
            'school': cond.get('school'),
            'gender': cond.get('gender')
        }
        
        # 验证年份范围
        if condition['year_range'] and len(condition['year_range']) != 2:
            print(f"警告: 无效的年份范围 {condition['year_range']}, 应包含两个年份")
            condition['year_range'] = []
        
        conditions.append(condition)
    
    # 添加全局逻辑
    global_logic = {
        'mode': config.get('logic', 'all'),
        'limit': config.get('limit', 0),
        'output_fields': config.get('output_fields', ['name', 'records'])
    }
    
    return conditions, global_logic

def match_condition(record, condition):
    """检查记录是否满足单个条件"""
    # 检查比赛类型
    if record.contest.type != condition['contest_type']:
        return False
    
    # 检查奖项
    if condition['award'] and record.level != condition['award']:
        return False
    
    # 检查最低奖项
    if condition['min_award']:
        award_levels = {
            "金牌": 5, "银牌": 4, "铜牌": 3, 
            "一等奖": 3, "二等奖": 2, "三等奖": 1
        }
        record_level = award_levels.get(record.level, 0)
        min_level = award_levels.get(condition['min_award'], 0)
        if record_level < min_level:
            return False
    
    # 检查年份范围
    if condition['year_range']:
        start_year, end_year = condition['year_range']
        if not (start_year <= record.contest.year <= end_year):
            return False
    
    # 检查省份
    if condition['province'] and record.province != condition['province']:
        return False
    
    # 检查学校
    if condition['school'] and record.school.name != condition['school']:
        return False
    
    # 检查性别
    if condition['gender']:
        gender_map = {"男": 1, "女": -1, "其他": 0}
        gender_value = gender_map.get(condition['gender'], 0)
        if record.gender != gender_value:
            return False
    
    return True

def find_oiers_by_conditions(conditions, logic, oiers):
    """根据条件筛选选手"""
    results = []
    mode = logic['mode']  # 'all' 或 'any'
    limit = logic['limit']  # 结果数量限制
    
    for oier in oiers:
        # 检查是否满足条件
        matches = 0
        matched_records = {}
        
        # 检查每个条件
        for idx, condition in enumerate(conditions):
            for record in oier.records:
                if match_condition(record, condition):
                    matches += 1
                    matched_records[idx] = record
                    break  # 每个条件只需匹配一个记录
        
        # 根据逻辑模式判断
        if mode == 'all' and matches == len(conditions):
            results.append((oier, matched_records))
        elif mode == 'any' and matches > 0:
            results.append((oier, matched_records))
        
        # 检查结果数量限制
        if limit > 0 and len(results) >= limit:
            break
    
    return results

def format_output(oier, matched_records, conditions, output_fields):
    """格式化输出单个选手的结果"""
    output = {}
    
    # 基本字段
    if 'name' in output_fields:
        output['name'] = oier.name
    if 'uid' in output_fields:
        output['uid'] = oier.uid
    if 'enroll_middle' in output_fields:
        output['enroll_middle'] = oier.enroll_middle
    if 'oierdb_score' in output_fields and hasattr(oier, 'oierdb_score'):
        output['oierdb_score'] = float(oier.oierdb_score)
    if 'ccf_score' in output_fields and hasattr(oier, 'ccf_score'):
        output['ccf_score'] = float(oier.ccf_score)
    if 'ccf_level' in output_fields and hasattr(oier, 'ccf_level'):
        output['ccf_level'] = oier.ccf_level
    
    # 匹配的记录
    if 'matched_records' in output_fields:
        output['matched_records'] = {}
        for idx, record in matched_records.items():
            cond = conditions[idx]
            record_info = {
                'contest_name': record.contest.name,
                'contest_type': record.contest.type,
                'year': record.contest.year,
                'award': record.level,
                'score': record.score,
                'rank': record.rank,
                'province': record.province,
                'school': record.school.name if record.school else None
            }
            output['matched_records'][idx] = record_info
    
    # 所有记录
    if 'all_records' in output_fields:
        output['all_records'] = []
        for record in oier.records:
            record_info = {
                'contest_name': record.contest.name,
                'contest_type': record.contest.type,
                'year': record.contest.year,
                'award': record.level,
                'score': record.score,
                'rank': record.rank,
                'province': record.province,
                'school': record.school.name if record.school else None
            }
            output['all_records'].append(record_info)
    
    return output

def print_results(results, conditions, logic):
    """打印筛选结果"""
    if not results:
        print("\n没有找到满足条件的选手")
        return
    
    mode_str = "所有" if logic['mode'] == 'all' else "任一"
    print(f"\n找到 {len(results)} 位满足{mode_str}条件的选手:")
    
    for oier, matched_records in results:
        print(f"\n选手: {oier.name} (UID: {oier.uid}, 入学年份: {oier.enroll_middle})")
        
        # 打印匹配的记录
        print("满足条件的比赛记录:")
        for idx, record in matched_records.items():
            cond = conditions[idx]
            cond_desc = f"条件{idx+1}: {cond['contest_type']}"
            if cond['award']:
                cond_desc += f"({cond['award']})"
            elif cond['min_award']:
                cond_desc += f"({cond['min_award']}及以上)"
            
            print(f"  - {cond_desc}: {record.contest.name} ({record.contest.year}年) "
                  f"奖项: {record.level}, 分数: {record.score}, 排名: {record.rank}")
        
        print("-" * 80)

def export_to_csv(results, conditions, logic, filename):
    """将结果导出为CSV文件"""
    import csv
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # 写入标题行
        headers = ['选手姓名', 'UID', '入学年份', 'DB评分', 'CCF评分', 'CCF等级']
        for idx in range(len(conditions)):
            headers.append(f'条件{idx+1}_比赛')
            headers.append(f'条件{idx+1}_年份')
            headers.append(f'条件{idx+1}_奖项')
            headers.append(f'条件{idx+1}_分数')
            headers.append(f'条件{idx+1}_排名')
        writer.writerow(headers)
        
        # 写入数据行
        for oier, matched_records in results:
            row = [
                oier.name,
                oier.uid,
                oier.enroll_middle,
                getattr(oier, 'oierdb_score', ''),
                getattr(oier, 'ccf_score', ''),
                getattr(oier, 'ccf_level', '')
            ]
            
            # 为每个条件添加匹配记录信息
            for idx in range(len(conditions)):
                if idx in matched_records:
                    record = matched_records[idx]
                    row.extend([
                        record.contest.name,
                        record.contest.year,
                        record.level,
                        record.score,
                        record.rank
                    ])
                else:
                    row.extend(['', '', '', '', ''])
            
            writer.writerow(row)
    
    print(f"\n结果已导出到 {filename}")

def main():
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='根据YAML配置筛选选手')
    parser.add_argument('--data', default='data/serialized_data.pkl', 
                        help='序列化数据文件路径 (默认: data/serialized_data.pkl)')
    parser.add_argument('--config', required=True, help='YAML配置文件路径')
    parser.add_argument('--output', help='结果输出文件路径 (CSV格式)')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    args = parser.parse_args()
    
    # 解析配置条件
    config = parse_conditions(args.config)
    if not config:
        return
    
    conditions, logic = config
    
    # 打印条件摘要
    print("\n筛选条件:")
    for idx, cond in enumerate(conditions):
        cond_desc = f"{idx+1}. 比赛类型: {cond['contest_type']}"
        if cond['award']:
            cond_desc += f", 奖项: {cond['award']}"
        elif cond['min_award']:
            cond_desc += f", 最低奖项: {cond['min_award']}"
        if cond['year_range']:
            cond_desc += f", 年份范围: {cond['year_range'][0]}-{cond['year_range'][1]}"
        if cond['province']:
            cond_desc += f", 省份: {cond['province']}"
        if cond['school']:
            cond_desc += f", 学校: {cond['school']}"
        if cond['gender']:
            cond_desc += f", 性别: {cond['gender']}"
        print(f"  - {cond_desc}")
    
    print(f"逻辑模式: {logic['mode']}, 结果限制: {logic['limit']}")
    
    # 加载数据
    print(f"\n正在从 {args.data} 加载数据...")
    data = load_data(args.data)
    if not data:
        return
    
    print(f"数据加载成功! 选手数量: {len(data['oiers'])}, 比赛数量: {len(data['contests'])}")
    
    # 筛选选手
    results = find_oiers_by_conditions(conditions, logic, data['oiers'])
    
    # 输出结果
    print(f"\n找到 {len(results)} 位满足条件的选手")
    
    if args.debug:
        print_results(results, conditions, logic)
    
    # 导出结果
    if args.output:
        export_to_csv(results, conditions, logic, args.output)
    else:
        # 默认输出前10位选手的摘要
        print("\n前10位满足条件的选手:")
        for oier, _ in results[:10]:
            print(f"- {oier.name} (UID: {oier.uid}, 入学年份: {oier.enroll_middle})")
        
        if len(results) > 10:
            print(f"... 以及另外 {len(results)-10} 位选手")

if __name__ == "__main__":
    main()