# create_indexes.py
import requests
import yaml
import json
import os
def load_config():
    """读取配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
def execute_d1_sql(cfg, sql):
    """执行 SQL 到 Cloudflare D1"""
    account_id = cfg['cloudflare']['account_id']
    database_id = cfg['cloudflare']['database_id']
    api_token = cfg['cloudflare']['api_token']
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/raw"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    payload = { "sql": sql }
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        resp.raise_for_status() # 如果状态码不是 2xx，则抛出异常
    except requests.exceptions.RequestException as e:
        print(f"❌ API 请求失败: {e}")
        return False
    data = resp.json()
    all_success = True
    for result in data.get("result", []):
        if not result.get("success", False):
            print(f"❌ SQL 语句执行失败: {result}")
            all_success = False
            
    if not data.get("success", False) and not isinstance(data.get("result"), list):
         print(f"❌ SQL 执行失败: {data}")
         return False
         
    return all_success
def main():
    """主函数，创建所有必要的索引"""
    try:
        cfg = load_config()
    except FileNotFoundError:
        print("❌ 错误: 未找到 config.yml 配置文件。")
        return
    except Exception as e:
        print(f"❌ 读取配置文件时出错: {e}")
        return
    print("🚀 准备为数据库创建和优化索引...")
    
    # --- 最终的、完整的索引定义 ---
    # 分组注释，方便理解每个索引的作用
    index_sql = """
    -- === Record 表索引 ===
    
    -- [核心优化-1] 用于内存验证阶段(verification mode)，根据 oier_uid 快速获取其所有记录。
    -- 这是一个覆盖索引，包含了内存过滤所需的所有 Record 表字段和 JOIN 键，避免回表。
    CREATE INDEX IF NOT EXISTS idx_record_oier_covering ON 
    Record(oier_uid, contest_id, level, score, rank, province, school_id);
    -- [核心优化-2] 用于数据库过滤阶段，当查询以比赛年份/类型等条件开始时，
    -- 极大加速 Record 与 Contest 表的 JOIN 操作。
    CREATE INDEX IF NOT EXISTS idx_record_contest_oier ON Record(contest_id, oier_uid);
    -- [核心优化-3] 用于数据库过滤阶段，当查询以省份为主要条件时。
    -- (覆盖索引，包含oier_uid以避免回表)
    CREATE INDEX IF NOT EXISTS idx_record_province_oier ON Record(province, oier_uid);
    -- [核心优化-4] 用于数据库过滤阶段，当查询以学校为主要条件时。
    -- (覆盖索引，包含oier_uid以避免回表)
    CREATE INDEX IF NOT EXISTS idx_record_school_oier ON Record(school_id, oier_uid);
    
    -- [组合查询] 原始的复合索引，对多个字段(level, province, score)组合的复杂查询依然有价值。
    CREATE INDEX IF NOT EXISTS idx_record_query ON Record(level, province, score, contest_id, oier_uid);
    -- === Contest 表索引 ===
    
    -- 加速基于年份和类型的比赛查找。'id' 包含在末尾可以帮助某些查询计划。
    CREATE INDEX IF NOT EXISTS idx_contest_year_type ON Contest(year, type, id);

    -- === OIer 表索引 ===

    -- [修改] 优化 OIer 表的索引以支持 gender, enroll_middle 和 initials 的联合查询。
    -- 这个索引对于在第一次查询时预筛选 OIer 至关重要。uid 包含在末尾有助于 JOIN 操作。
    CREATE INDEX IF NOT EXISTS idx_oier_filters ON OIer(gender, enroll_middle, initials, uid);
    """
    print("执行以下SQL语句:\n" + "="*30 + index_sql + "="*30)
    
    if execute_d1_sql(cfg, index_sql):
        print("\n✅ 所有索引成功创建或已存在。")
    else:
        print("\n⚠ 索引创建过程中出现错误，请检查上面的日志。")
if __name__ == "__main__":
    main()