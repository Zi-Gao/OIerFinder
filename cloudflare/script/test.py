import os
import sqlite3
import requests
import json
import time
import yaml
import math  # 引入 math 库用于检查 NaN 和 Infinity
from tqdm import tqdm

def load_config(path='config.yml'):
    # ... (此函数无变化)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ 错误: 配置文件 '{path}' 未找到。")
        exit(1)
    except yaml.YAMLError as e:
        print(f"❌ 错误: 配置文件 '{path}' 格式错误: {e}")
        exit(1)

# --- 配置 (无变化) ---
CONFIG = load_config()
CF_CONFIG = CONFIG.get('cloudflare', {})
DB_CONFIG = CONFIG.get('database', {})
SETTINGS = CONFIG.get('settings', {})

CF_ACCOUNT_ID = CF_CONFIG.get('account_id')
CF_DATABASE_ID = CF_CONFIG.get('database_id')
CF_API_TOKEN = CF_CONFIG.get('api_token')

LOCAL_DB_PATH = DB_CONFIG.get('local_path', 'oier.db')
BATCH_SIZE = SETTINGS.get('batch_size', 1000)

D1_QUERY_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/d1/database/{CF_DATABASE_ID}/query"
HEADERS = { "Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json" }

# --- 数据库 Schema (无变化) ---
TABLE_DEFINITIONS = { # ... 省略 ...
}
TABLE_ORDER = ["OIer", "Contest", "School", "Record"]
TABLE_DEFINITIONS = {
    "OIer": "CREATE TABLE OIer (uid INTEGER PRIMARY KEY, name TEXT, initials TEXT, gender INTEGER, enroll_middle INTEGER, oierdb_score REAL, ccf_score REAL, ccf_level INTEGER);",
    "Contest": "CREATE TABLE Contest (id INTEGER PRIMARY KEY, name TEXT, type TEXT, year INTEGER, fall_semester INTEGER, full_score INTEGER);",
    "School": "CREATE TABLE School (id INTEGER PRIMARY KEY, name TEXT, province TEXT, city TEXT, score REAL);",
    "Record": "CREATE TABLE Record (id INTEGER PRIMARY KEY AUTOINCREMENT, oier_uid INTEGER, contest_id INTEGER, school_id INTEGER, score REAL, rank INTEGER, province TEXT, level TEXT, FOREIGN KEY (oier_uid) REFERENCES OIer (uid), FOREIGN KEY (contest_id) REFERENCES Contest (id), FOREIGN KEY (school_id) REFERENCES School (id));"
}


def run_single_query_on_d1(sql_statement):
    # ... (此函数无变化)
    payload = {"sql": sql_statement}
    try:
        response = requests.post(D1_QUERY_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            print(f"\n❌ D1 查询执行失败: {sql_statement[:80]}...")
            for res in result.get("result", []):
                if not res.get("success"):
                    print(json.dumps(res.get("meta", {}), indent=2))
            return False
        return True
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 单个查询请求失败: {e}")
        if e.response: print(f"   响应: {e.response.text}")
        return False

# --- vvvvvvvvvvvvvvvv 核心修改点 vvvvvvvvvvvvvvvv ---

def clean_value(value):
    """将 NaN 或 Infinity 浮点数转换为 None (即 SQL NULL)"""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value

def batch_insert_to_d1(table_name, columns, data_batch):
    """(已修正) 向 D1 批量插入数据，增加了数据清洗步骤"""
    if not data_batch: return True
    
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders});"
    
    # 数据清洗：在发送前处理每一行数据
    cleaned_params = []
    for row in data_batch:
        # 对行中的每个值应用清洗函数
        cleaned_row = [clean_value(value) for value in row]
        cleaned_params.append(cleaned_row)
        
    payload = {"sql": sql, "params": cleaned_params} # 使用清洗后的数据
    
    try:
        response = requests.post(D1_QUERY_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            print(f"\n❌ D1 批量插入表 '{table_name}' 失败")
            # 打印更详细的错误帮助调试
            if result.get("result"):
                for res_item in result["result"]:
                    if not res_item.get("success"):
                        print(json.dumps(res_item.get("meta"), indent=2))
            return False
        return True
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 批量插入时网络错误: {e}")
        if e.response: 
            print(f"   响应状态码: {e.response.status_code}")
            try:
                print(f"   响应内容: {json.dumps(e.response.json(), indent=2)}")
            except json.JSONDecodeError:
                print(f"   响应内容: {e.response.text}")
        return False

# --- ^^^^^^^^^^^^^^^^ 核心修改点 ^^^^^^^^^^^^^^^^ ---


def transfer_table_data(local_conn, table_name):
    # ... (此函数无变化)
    print(f"\n🚚 开始传输表: {table_name}")
    local_cursor = local_conn.cursor()
    total_rows = local_cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    if total_rows == 0:
        print(f"🔵 表 '{table_name}' 为空，跳过。")
        return
    local_cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [row[1] for row in local_cursor.fetchall()]
    local_cursor.execute(f"SELECT * FROM {table_name};")
    with tqdm(total=total_rows, desc=f"  上传 {table_name}", unit="行") as pbar:
        while True:
            batch = local_cursor.fetchmany(BATCH_SIZE)
            if not batch: break
            if not batch_insert_to_d1(table_name, columns, batch):
                print(f"❗️ 停止传输表 '{table_name}' 因为发生错误。")
                break
            pbar.update(len(batch))

def main():
    # ... (此函数无变化)
    print("🚀 开始数据迁移至 Cloudflare D1 (数据清洗版)")
    if not all([CF_ACCOUNT_ID, CF_DATABASE_ID, CF_API_TOKEN]):
        print("❌ 错误: 缺少 Cloudflare 配置。请检查你的 config.yml 文件。")
        return
    if not os.path.exists(LOCAL_DB_PATH):
        print(f"❌ 错误: 本地数据库文件 '{LOCAL_DB_PATH}' 不存在。")
        return

    print("\n PHASE 1: 正在 D1 上重建表结构...")
    print("  - 正在删除旧表...")
    for table in reversed(TABLE_ORDER):
        if not run_single_query_on_d1(f"DROP TABLE IF EXISTS {table};"):
            print(f"❌ 删除表 {table} 失败，程序终止。")
            return
    print("  - 正在创建新表...")
    for table in TABLE_ORDER:
        if not run_single_query_on_d1(TABLE_DEFINITIONS[table]):
            print(f"❌ 创建表 {table} 失败，程序终止。")
            return
    print("✅ 表结构重建成功！")

    print("\n PHASE 2: 正在传输数据...")
    try:
        local_conn = sqlite3.connect(LOCAL_DB_PATH)
        for table_name in TABLE_ORDER:
            transfer_table_data(local_conn, table_name)
    except sqlite3.Error as e:
        print(f"❌ 连接或读取本地 SQLite 数据库时出错: {e}")
    finally:
        if 'local_conn' in locals() and local_conn:
            local_conn.close()

    print("\n✨ 所有数据传输完成！")


if __name__ == "__main__":
    main()
