import sqlite3
import os
import argparse
import yaml

# 导入重构后的核心逻辑
import finder_engine

DB_FILE = 'oier_data.db'
DEFAULT_CONFIG_FILE = 'config.yml'

def load_config(config_file):
    """加载 YAML 配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"错误: 配置文件 '{config_file}' 未找到。")
        return None
    except yaml.YAMLError as e:
        print(f"错误: 解析 YAML 文件 '{config_file}' 失败: {e}")
        return None

def print_results(oiers):
    """格式化并打印结果"""
    if not oiers:
        print("\n======================================")
        print("未找到符合所有条件的 OIer。")
        print("======================================")
        return

    print(f"\n======================================")
    print(f"找到 {len(oiers)} 名符合所有条件的 OIer:")
    print("======================================")
    print(f"{'UID':<8} {'姓名':<10} {'性别':<4} {'入学年份':<8} {'DB评分':<10}")
    print("-" * 50)
    
    gender_map = {1: '男', -1: '女', 0: '未知'}
    
    for oier_row in oiers:
        # 将 sqlite3.Row 对象转换为字典以便访问
        oier = dict(oier_row)
        uid = oier.get('uid')
        name = oier.get('name')
        gender = oier.get('gender')
        enroll = oier.get('enroll_middle')
        score = oier.get('oierdb_score', 0)
        
        print(f"{uid:<8} {name:<10} {gender_map.get(gender, '?'):<4} {enroll:<8} {score:<10.2f}")

def main():
    parser = argparse.ArgumentParser(description="根据 YAML 配置查询 OIer 数据。")
    parser.add_argument(
        '-c', '--config',
        default=DEFAULT_CONFIG_FILE,
        help=f"指定 YAML 配置文件路径 (默认为: {DEFAULT_CONFIG_FILE})"
    )
    args = parser.parse_args()

    if not os.path.exists(DB_FILE):
        print(f"错误: 数据库文件 '{DB_FILE}' 不存在。请先运行 create_db.py。")
        return

    config = load_config(args.config)
    if config is None:
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        # 让返回结果可以像字典一样访问，方便打印
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print(f"--- 开始使用 '{args.config}' 进行查询 ---")
        
        # 调用核心查询引擎
        found_oiers = finder_engine.find_oiers(config, cursor)
        
        print_results(found_oiers)
        
        print("\n--- 查询结束 ---")

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    main()