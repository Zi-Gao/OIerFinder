import math
import os
import sqlite3

import requests
import yaml
from tqdm import tqdm


REQUEST_TIMEOUT_SECONDS = 60
STAGING_SUFFIX = "__staging"

TABLES = [
    ("OIer", ["uid", "name", "initials", "gender", "enroll_middle", "oierdb_score", "ccf_score", "ccf_level"]),
    ("Contest", ["id", "name", "type", "year", "fall_semester", "full_score"]),
    ("School", ["id", "name", "province", "city", "score"]),
    ("Record", ["id", "oier_uid", "contest_id", "school_id", "score", "rank", "province", "level"]),
]

CORE_SCHEMA = {
    "OIer": """
        CREATE TABLE IF NOT EXISTS OIer (
            uid INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            initials TEXT,
            gender INTEGER,
            enroll_middle INTEGER,
            oierdb_score REAL,
            ccf_score REAL,
            ccf_level INTEGER
        )
    """,
    "Contest": """
        CREATE TABLE IF NOT EXISTS Contest (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            year INTEGER,
            fall_semester INTEGER,
            full_score INTEGER
        )
    """,
    "School": """
        CREATE TABLE IF NOT EXISTS School (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            province TEXT,
            city TEXT,
            score REAL
        )
    """,
    "Record": """
        CREATE TABLE IF NOT EXISTS Record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oier_uid INTEGER,
            contest_id INTEGER,
            school_id INTEGER,
            score REAL,
            rank INTEGER,
            province TEXT,
            level TEXT,
            FOREIGN KEY (oier_uid) REFERENCES OIer (uid),
            FOREIGN KEY (contest_id) REFERENCES Contest (id),
            FOREIGN KEY (school_id) REFERENCES School (id)
        )
    """,
}

STAGING_SCHEMA = {
    "OIer": """
        CREATE TABLE OIer__staging (
            uid INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            initials TEXT,
            gender INTEGER,
            enroll_middle INTEGER,
            oierdb_score REAL,
            ccf_score REAL,
            ccf_level INTEGER
        )
    """,
    "Contest": """
        CREATE TABLE Contest__staging (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            year INTEGER,
            fall_semester INTEGER,
            full_score INTEGER
        )
    """,
    "School": """
        CREATE TABLE School__staging (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            province TEXT,
            city TEXT,
            score REAL
        )
    """,
    "Record": """
        CREATE TABLE Record__staging (
            id INTEGER PRIMARY KEY,
            oier_uid INTEGER,
            contest_id INTEGER,
            school_id INTEGER,
            score REAL,
            rank INTEGER,
            province TEXT,
            level TEXT
        )
    """,
}


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _d1_url(cfg, endpoint):
    cloudflare = cfg["cloudflare"]
    return (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{cloudflare['account_id']}/d1/database/{cloudflare['database_id']}/{endpoint}"
    )


def _execute_d1_request(cfg, endpoint, payload):
    response = requests.post(
        _d1_url(cfg, endpoint),
        headers={
            "Authorization": f"Bearer {cfg['cloudflare']['api_token']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("success", False):
        raise RuntimeError(f"Cloudflare D1 API 请求失败: {data.get('errors', data)}")

    results = data.get("result")
    if not isinstance(results, list) or not results:
        raise RuntimeError(f"Cloudflare D1 返回了空或无效的执行结果: {data}")

    failed_results = [
        result for result in results
        if not result.get("success", False)
    ]
    if failed_results:
        raise RuntimeError(f"Cloudflare D1 SQL 执行失败: {failed_results}")
    return data


def execute_d1_sql(cfg, sql):
    return _execute_d1_request(cfg, "raw", {"sql": sql})


def execute_d1_batch(cfg, statements):
    batch = [
        statement if isinstance(statement, dict) else {"sql": statement}
        for statement in statements
    ]
    return _execute_d1_request(cfg, "query", {"batch": batch})


def validate_local_database(connection):
    counts = {}
    cursor = connection.cursor()

    for table_name, expected_columns in TABLES:
        actual_columns = {
            row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")
        }
        missing_columns = set(expected_columns) - actual_columns
        if missing_columns:
            raise RuntimeError(
                f"本地表 {table_name} 缺少字段: {sorted(missing_columns)}"
            )

        count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        if count <= 0:
            raise RuntimeError(f"本地表 {table_name} 为空，拒绝覆盖生产数据库")
        counts[table_name] = count

    foreign_key_errors = cursor.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise RuntimeError(
            f"本地数据库存在 {len(foreign_key_errors)} 条外键错误，拒绝上传"
        )

    return counts


def ensure_remote_schema(cfg):
    execute_d1_batch(cfg, [CORE_SCHEMA[table_name] for table_name, _ in TABLES])


def prepare_staging_tables(cfg):
    statements = []
    for table_name, _ in reversed(TABLES):
        statements.append(f"DROP TABLE IF EXISTS {table_name}{STAGING_SUFFIX}")
    for table_name, _ in TABLES:
        statements.append(STAGING_SCHEMA[table_name])
    execute_d1_batch(cfg, statements)


def sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"不能上传非有限浮点数: {value}")
    return str(value)


def transfer_table(connection, table_name, columns, cfg):
    target_table = f"{table_name}{STAGING_SUFFIX}"
    print(f"🚀 上传暂存表: {target_table}")
    cursor = connection.cursor()
    cursor.execute(f"SELECT {', '.join(columns)} FROM {table_name}")

    batch_size = int(cfg["settings"]["batch_size"])
    if batch_size <= 0:
        raise ValueError("settings.batch_size 必须是正整数")

    total_rows = connection.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()[0]
    batch = []
    progress = tqdm(total=total_rows, desc=table_name, unit="rows", ncols=80)

    try:
        for row in cursor:
            values = ", ".join(sql_literal(value) for value in row)
            batch.append(
                f"INSERT INTO {target_table} ({', '.join(columns)}) VALUES ({values})"
            )
            progress.update(1)

            if len(batch) >= batch_size:
                execute_d1_sql(cfg, ";\n".join(batch))
                batch = []

        if batch:
            execute_d1_sql(cfg, ";\n".join(batch))
    finally:
        progress.close()

    print(f"✅ 完成上传暂存表 {target_table}")


def get_remote_table_count(cfg, table_name):
    data = _execute_d1_request(
        cfg,
        "query",
        {"sql": f"SELECT COUNT(*) AS count FROM {table_name}"},
    )
    results = data["result"][0].get("results", [])
    if not results:
        raise RuntimeError(f"无法读取远端表 {table_name} 的行数")
    return int(results[0]["count"])


def verify_staging_tables(cfg, expected_counts):
    for table_name, expected_count in expected_counts.items():
        staging_table = f"{table_name}{STAGING_SUFFIX}"
        actual_count = get_remote_table_count(cfg, staging_table)
        if actual_count != expected_count:
            raise RuntimeError(
                f"暂存表 {staging_table} 行数不一致: "
                f"本地 {expected_count}, 远端 {actual_count}"
            )


def promote_staging_tables(cfg):
    statements = []
    for table_name, _ in reversed(TABLES):
        statements.append(f"DELETE FROM {table_name}")
    for table_name, columns in TABLES:
        column_list = ", ".join(columns)
        statements.append(
            f"INSERT INTO {table_name} ({column_list}) "
            f"SELECT {column_list} FROM {table_name}{STAGING_SUFFIX}"
        )
    for table_name, _ in reversed(TABLES):
        statements.append(f"DROP TABLE {table_name}{STAGING_SUFFIX}")

    # Cloudflare D1 batch 是事务：任一语句失败会回滚整批，旧生产数据保持不变。
    execute_d1_batch(cfg, statements)


def main():
    cfg = load_config()
    db_path = cfg["database"]["local_path"]
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), db_path))
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"找不到 SQLite 文件: {db_path}")

    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        print("🔍 正在验证本地数据库...")
        expected_counts = validate_local_database(connection)

        print("🧱 正在确保远端表结构存在...")
        ensure_remote_schema(cfg)

        print("📦 正在准备远端暂存表...")
        prepare_staging_tables(cfg)

        for table_name, columns in TABLES:
            transfer_table(connection, table_name, columns, cfg)

        print("🔎 正在核对远端暂存表...")
        verify_staging_tables(cfg, expected_counts)

        print("🔄 正在以事务方式替换生产数据...")
        promote_staging_tables(cfg)
    finally:
        connection.close()

    print("🎉 全部上传并原子替换完成")


if __name__ == "__main__":
    main()
