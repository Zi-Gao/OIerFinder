import sqlite3
import requests
import yaml
import os
import json
from tqdm import tqdm

# 读取配置文件
def load_config():
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# 执行批量 SQL 到 Cloudflare D1
def execute_d1_sql(api_token, account_id, database_id, sql_batch):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/raw"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "sql": sql_batch
    }
    resp = requests.post(url, headers=headers, data=json.dumps(payload))
    if resp.status_code != 200:
        print("\n❌ Cloudflare API 请求失败:", resp.text)
        return False
    data = resp.json()
    if not data.get("success", False):
        print("\n❌ SQL 执行错误:", data)
        return False
    return True

# 清空 Cloudflare D1 所有表数据
def clear_all_tables(cfg):
    sql = """
    PRAGMA foreign_keys = OFF;
    DELETE FROM Record;
    DELETE FROM OIer;
    DELETE FROM Contest;
    DELETE FROM School;
    PRAGMA foreign_keys = ON;
    """
    print("⚠ 正在清空 Cloudflare D1 所有数据...")
    return execute_d1_sql(cfg["cloudflare"]["api_token"],
                          cfg["cloudflare"]["account_id"],
                          cfg["cloudflare"]["database_id"], sql)

# 上传 SQLite 表到 Cloudflare D1
def transfer_table(connection, table_name, columns, cfg):
    print(f"🚀 上传表: {table_name}")
    cursor = connection.cursor()
    cursor.execute(f"SELECT {', '.join(columns)} FROM {table_name}")
    batch_size = cfg["settings"]["batch_size"]
    conflict_strategy = cfg["settings"].get("on_conflict", "IGNORE")  # IGNORE / REPLACE

    # 查询总行数（用于进度条）
    cursor_count = connection.cursor()
    cursor_count.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = cursor_count.fetchone()[0]

    batch = []
    progress = tqdm(total=total_rows, desc=f"{table_name}", unit="rows", ncols=80)

    for row in cursor:
        values = []
        for v in row:
            if v is None:
                values.append("NULL")
            elif isinstance(v, str):
                safe_str = v.replace("'", "''")
                values.append(f"'{safe_str}'")
            else:
                values.append(str(v))
        sql = f"INSERT OR {conflict_strategy} INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(values)});"
        batch.append(sql)
        progress.update(1)

        if len(batch) >= batch_size:
            if not execute_d1_sql(cfg["cloudflare"]["api_token"],
                                  cfg["cloudflare"]["account_id"],
                                  cfg["cloudflare"]["database_id"],
                                  "\n".join(batch)):
                progress.close()
                raise RuntimeError(f"上传 {table_name} 失败")
            batch = []

    # 上传剩余的
    if batch:
        if not execute_d1_sql(cfg["cloudflare"]["api_token"],
                              cfg["cloudflare"]["account_id"],
                              cfg["cloudflare"]["database_id"],
                              "\n".join(batch)):
            progress.close()
            raise RuntimeError(f"上传 {table_name} 失败")

    progress.close()
    print(f"✅ 完成上传表 {table_name}")

# 主函数
def main():
    cfg = load_config()
    db_path = cfg["database"]["local_path"]
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"找不到 SQLite 文件: {db_path}")

    # 如果配置了 clear_before_import 就清空表
    if cfg["settings"].get("clear_before_import", False):
        if not clear_all_tables(cfg):
            raise RuntimeError("清空 Cloudflare D1 数据失败")
        print("✅ 数据库已清空")

    conn = sqlite3.connect(db_path)

    # 按外键顺序上传（主表 → 从表）
    tables = [
        ("OIer", ["uid", "name", "initials", "gender", "enroll_middle", "oierdb_score", "ccf_score", "ccf_level"]),
        ("Contest", ["id", "name", "type", "year", "fall_semester", "full_score"]),
        ("School", ["id", "name", "province", "city", "score"]),
        ("Record", ["id", "oier_uid", "contest_id", "school_id", "score", "rank", "province", "level"])
    ]

    for table, cols in tables:
        transfer_table(conn, table, cols, cfg)

    conn.close()
    print("🎉 全部上传完成")

if __name__ == "__main__":
    main()