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

def match_condition(record, condition):
    """检查记录是否满足单个条件"""
    # 确保condition是字典
    if not isinstance(condition, dict):
        return False
    
    # 检查比赛类型
    if 'contest_type' not in condition:
        return False
    if record.contest.type != condition['contest_type']:
        return False
    
    # 检查奖项
    if condition.get('award') and record.level != condition['award']:
        return False
    
    # 检查最低奖项
    if condition.get('min_award'):
        award_levels = {
            "金牌": 5, "银牌": 4, "铜牌": 3, 
            "一等奖": 3, "二等奖": 2, "三等奖": 1
        }
        record_level = award_levels.get(record.level, 0)
        min_level = award_levels.get(condition['min_award'], 0)
        if record_level < min_level:
            return False
    
    # 检查年份范围
    if condition.get('year_range') and len(condition['year_range']) == 2:
        start_year, end_year = condition['year_range']
        if not (start_year <= record.contest.year <= end_year):
            return False
    
    # 检查省份
    if condition.get('province') and record.province != condition['province']:
        return False
    
    # 检查学校
    if condition.get('school') and record.school.name != condition['school']:
        return False
    
    # 检查性别
    if condition.get('gender'):
        gender_map = {"男": 1, "女": -1, "其他": 0}
        gender_value = gender_map.get(condition['gender'], 0)
        if record.gender != gender_value:
            return False
    
    return True

def find_oiers_by_conditions(conditions, logic, oiers):
    """根据条件筛选选手"""
    results = []
    mode = logic.get('mode', 'all')  # 'all' 或 'any'
    limit = logic.get('limit', 0)  # 结果数量限制
    
    for oier in oiers:
        # 检查是否满足条件
        matches = 0
        matched_records = {}
        
        # 检查每个条件
        for idx, condition in enumerate(conditions):
            # 确保condition是字典
            if not isinstance(condition, dict):
                continue
                
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

def find_oiers_by_yaml_config(config, data_file):
    """根据YAML配置查询OIer"""
    # 加载数据
    data = load_data(data_file)
    if not data:
        raise Exception("无法加载数据")
    
    # 检查配置是否为字典
    if not isinstance(config, dict):
        raise Exception(f"配置格式错误：期望字典格式，实际得到 {type(config).__name__}")
    
    # 获取条件
    conditions = config.get('conditions', [])
    logic = config.get('logic', {})
    
    # 检查条件是否为列表
    if not isinstance(conditions, list):
        raise Exception(f"conditions 应该是一个列表，实际得到 {type(conditions).__name__}")
    
    # 检查每个条件是否为字典
    for i, condition in enumerate(conditions):
        if not isinstance(condition, dict):
            raise Exception(f"条件 {i+1} 应该是一个字典，实际得到 {type(condition).__name__}")
        
        # 确保 contest_type 存在且为字符串
        if 'contest_type' not in condition:
            raise Exception(f"条件 {i+1} 缺少 contest_type 字段")
        
        if not isinstance(condition['contest_type'], str):
            raise Exception(f"条件 {i+1} 的 contest_type 应该是字符串")
    
    # 检查逻辑配置
    if not isinstance(logic, dict):
        raise Exception(f"logic 应该是一个字典，实际得到 {type(logic).__name__}")
    
    # 确保logic有默认值
    if 'mode' not in logic:
        logic['mode'] = 'all'
    if 'limit' not in logic:
        logic['limit'] = 0
    
    # 筛选选手
    results = find_oiers_by_conditions(conditions, logic, data['oiers'])
    
    return results

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
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"解析YAML配置失败: {e}")
        return
    
    # 打印条件摘要
    print("\n筛选条件:")
    for idx, cond in enumerate(config.get('conditions', [])):
        cond_desc = f"{idx+1}. 比赛类型: {cond['contest_type']}"
        if 'award' in cond and cond['award']:
            cond_desc += f", 奖项: {cond['award']}"
        elif 'min_award' in cond and cond['min_award']:
            cond_desc += f", 最低奖项: {cond['min_award']}"
        if 'year_range' in cond and cond['year_range']:
            cond_desc += f", 年份范围: {cond['year_range'][0]}-{cond['year_range'][1]}"
        if 'province' in cond and cond['province']:
            cond_desc += f", 省份: {cond['province']}"
        if 'school' in cond and cond['school']:
            cond_desc += f", 学校: {cond['school']}"
        if 'gender' in cond and cond['gender']:
            cond_desc += f", 性别: {cond['gender']}"
        print(f"  - {cond_desc}")
    
    logic = config.get('logic', {})
    print(f"逻辑模式: {logic.get('mode', 'all')}, 结果限制: {logic.get('limit', 0)}")
    
    # 加载数据
    print(f"\n正在从 {args.data} 加载数据...")
    data = load_data(args.data)
    if not data:
        return
    
    print(f"数据加载成功! 选手数量: {len(data['oiers'])}, 比赛数量: {len(data['contests'])}")
    
    # 筛选选手
    results = find_oiers_by_yaml_config(config, args.data)
    
    # 输出结果
    print(f"\n找到 {len(results)} 位满足条件的选手")
    
    if args.debug:
        for oier, matched_records in results:
            print(f"\n选手: {oier.name} (UID: {oier.uid}, 入学年份: {oier.enroll_middle})")
            print("满足条件的比赛记录:")
            for idx, record in matched_records.items():
                cond = config['conditions'][idx]
                cond_desc = f"条件{idx+1}: {cond['contest_type']}"
                if 'award' in cond and cond['award']:
                    cond_desc += f"({cond['award']})"
                elif 'min_award' in cond and cond['min_award']:
                    cond_desc += f"({cond['min_award']}及以上)"
                
                print(f"  - {cond_desc}: {record.contest.name} ({record.contest.year}年) "
                      f"奖项: {record.level}, 分数: {record.score}, 排名: {record.rank}")
    
    # 导出结果
    if args.output:
        import csv
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入标题行
            headers = ['选手姓名', 'UID', '入学年份', 'DB评分', 'CCF评分', 'CCF等级']
            for idx in range(len(config.get('conditions', []))):
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
                for idx in range(len(config.get('conditions', []))):
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
        
        print(f"\n结果已导出到 {args.output}")
    else:
        # 默认输出前10位选手的摘要
        print("\n前10位满足条件的选手:")
        for oier, _ in results[:10]:
            print(f"- {oier.name} (UID: {oier.uid}, 入学年份: {oier.enroll_middle})")
        
        if len(results) > 10:
            print(f"... 以及另外 {len(results)-10} 位选手")

if __name__ == '__main__':
    main()