# create_indexes.py
import requests
import yaml
import json
import os
import sys
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
    try:
        data = resp.json()
    except requests.exceptions.JSONDecodeError as e:
        print(f"❌ API 返回了无效 JSON: {e}")
        return False

    if not data.get("success", False):
        print(f"❌ SQL 执行失败: {data.get('errors', data)}")
        return False

    results = data.get("result")
    if not isinstance(results, list) or not results:
        print(f"❌ SQL 执行结果为空或格式无效: {data}")
        return False

    all_success = True
    for result in results:
        if not result.get("success", False):
            print(f"❌ SQL 语句执行失败: {result}")
            all_success = False
    return all_success
def main():
    """主函数，创建所有必要的索引"""
    try:
        cfg = load_config()
    except FileNotFoundError:
        print("❌ 错误: 未找到 config.yml 配置文件。")
        return False
    except Exception as e:
        print(f"❌ 读取配置文件时出错: {e}")
        return False
    print("🚀 准备为数据库创建和优化索引...")
    # --- 最终的、完整的索引定义 ---
    # 分组注释，方便理解每个索引的作用
    index_sql = """
    -- === Record 表索引 ===
    -- [核心优化-1 / 内存验证]
    -- 用于内存验证模式 (verification mode)，根据 oier_uid 快速获取其所有记录。
    -- 这是一个完美的覆盖索引，包含了内存过滤所需的所有字段和JOIN键，完全避免回表。
    -- (此索引设计非常出色，予以保留)
    CREATE INDEX IF NOT EXISTS idx_record_oier_covering ON
    Record(oier_uid, contest_id, level, score, rank, province, school_id);

    -- [核心优化-2 / 初始查询入口 - 按比赛]
    -- 优化按 `contest_id` 和 `level` 的组合查询。这是非常常见的初始筛选条件。
    -- 作为覆盖索引，可以直接返回 oier_uid，避免回表。
    CREATE INDEX IF NOT EXISTS idx_record_contest_level_uid ON
    Record(contest_id, level, oier_uid);

    -- [核心优化-3 / 初始查询入口 - 按地域]
    -- 这是一个强大的复合索引，用于处理基于地域（学校、省份）的复杂查询。
    -- 字段顺序 (school_id, province) 遵循了从高选择性到低选择性的原则。
    -- 它可以高效地服务于：
    --   1. school_id = ?
    --   2. school_id = ? AND province = ?
    --   3. school_id = ? AND province = ? AND level = ?
    -- 同时也作为覆盖索引，避免回表。此索引可以替代旧的 idx_record_school_oier 和 idx_record_province_oier。
    CREATE INDEX IF NOT EXISTS idx_record_school_province_level_uid ON
    Record(school_id, province, level, oier_uid);


    -- === Contest 表索引 ===
    -- 加速基于年份和类型的比赛查找，用于初始查询的第一步 contest_id 预筛选。
    -- 'id' 包含在末尾使其成为覆盖索引，效率极高。
    -- (此索引设计非常出色，予以保留)
    CREATE INDEX IF NOT EXISTS idx_contest_year_type ON Contest(year, type, id);


    -- === OIer 表索引 ===
    -- 加速对 OIer 表的直接过滤（当没有 record_filters 时）或 JOIN 过程中的过滤。
    -- (这两个索引设计精准，予以保留)
    CREATE INDEX IF NOT EXISTS idx_oier_gender_enroll ON OIer(gender, enroll_middle, uid);
    CREATE INDEX IF NOT EXISTS idx_oier_initials_uid ON OIer(initials, uid);
    
    -- === 清理旧的/冗余的索引 (可选，但推荐) ===
    -- 在应用新索引后，可以安全地移除被替代的旧索引，以节省空间和写操作开销。
    DROP INDEX IF EXISTS idx_record_contest_oier;
    DROP INDEX IF EXISTS idx_record_province_oier;
    DROP INDEX IF EXISTS idx_record_school_oier;
    DROP INDEX IF EXISTS idx_record_query;
    """
    print("执行以下SQL语句:\n" + "="*30 + index_sql + "="*30)
    if execute_d1_sql(cfg, index_sql):
        print("\n✅ 所有索引成功创建或已存在。")
        return True
    else:
        print("\n⚠ 索引创建过程中出现错误，请检查上面的日志。")
        return False
if __name__ == "__main__":
    sys.exit(0 if main() else 1)
