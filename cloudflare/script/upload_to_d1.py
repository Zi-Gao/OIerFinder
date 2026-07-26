import argparse
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

RELEASE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS DataRelease (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        upstream_sha TEXT NOT NULL,
        data_hash TEXT NOT NULL,
        worker_version TEXT,
        status TEXT NOT NULL,
        oier_count INTEGER NOT NULL,
        contest_count INTEGER NOT NULL,
        school_count INTEGER NOT NULL,
        record_count INTEGER NOT NULL,
        github_run_url TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        activated_at TEXT
    )
"""


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    cloudflare = cfg.setdefault("cloudflare", {})
    database = cfg.setdefault("database", {})
    settings = cfg.setdefault("settings", {})

    environment_overrides = {
        "account_id": os.environ.get("CLOUDFLARE_ACCOUNT_ID"),
        "database_id": os.environ.get("CLOUDFLARE_DATABASE_ID"),
        "api_token": (
            os.environ.get("CLOUDFLARE_D1_API_TOKEN")
            or os.environ.get("CLOUDFLARE_API_TOKEN")
        ),
    }
    for key, value in environment_overrides.items():
        if value:
            cloudflare[key] = value

    if os.environ.get("OIER_DATABASE_PATH"):
        database["local_path"] = os.environ["OIER_DATABASE_PATH"]
    database.setdefault("local_path", "../../oier_data.db")

    if os.environ.get("D1_BATCH_SIZE"):
        settings["batch_size"] = int(os.environ["D1_BATCH_SIZE"])
    settings.setdefault("batch_size", 5000)

    missing_cloudflare_values = [
        key
        for key in ("account_id", "database_id", "api_token")
        if not cloudflare.get(key)
    ]
    if missing_cloudflare_values:
        raise RuntimeError(
            "缺少 Cloudflare 配置: "
            + ", ".join(missing_cloudflare_values)
            + "。请设置环境变量或 cloudflare/script/config.yml。"
        )

    return cfg


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
    execute_d1_sql(cfg, RELEASE_SCHEMA)


def get_release(cfg):
    execute_d1_sql(cfg, RELEASE_SCHEMA)
    data = _execute_d1_request(
        cfg,
        "query",
        {
            "sql": (
                "SELECT upstream_sha, data_hash, worker_version, status, "
                "oier_count, contest_count, school_count, record_count, "
                "github_run_url, updated_at, activated_at "
                "FROM DataRelease WHERE id = 1"
            )
        },
    )
    results = data["result"][0].get("results", [])
    return results[0] if results else None


def get_active_release_sha(cfg):
    release = get_release(cfg)
    if not release or release.get("status") != "active":
        return ""
    return release.get("upstream_sha", "")


def activate_release(cfg, source_sha):
    execute_d1_batch(
        cfg,
        [
            {
                "sql": (
                    "UPDATE DataRelease "
                    "SET status = 'active', activated_at = CURRENT_TIMESTAMP, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = 1 AND upstream_sha = ?1"
                ),
                "params": [source_sha],
            }
        ],
    )
    release = get_release(cfg)
    if (
        not release
        or release.get("upstream_sha") != source_sha
        or release.get("status") != "active"
    ):
        raise RuntimeError("无法激活指定的数据发布版本")


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


def promote_staging_tables(cfg, expected_counts, release_metadata=None):
    statements = []
    for table_name, _ in reversed(TABLES):
        statements.append(f"DELETE FROM {table_name}")
    for table_name, columns in TABLES:
        column_list = ", ".join(columns)
        statements.append(
            f"INSERT INTO {table_name} ({column_list}) "
            f"SELECT {column_list} FROM {table_name}{STAGING_SUFFIX}"
        )
    if release_metadata:
        statements.append(
            {
                "sql": """
                    INSERT INTO DataRelease (
                        id, upstream_sha, data_hash, worker_version, status,
                        oier_count, contest_count, school_count, record_count,
                        github_run_url, updated_at, activated_at
                    )
                    VALUES (
                        1, ?1, ?2, ?3, 'promoted',
                        ?4, ?5, ?6, ?7, ?8, CURRENT_TIMESTAMP, NULL
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        upstream_sha = excluded.upstream_sha,
                        data_hash = excluded.data_hash,
                        worker_version = excluded.worker_version,
                        status = excluded.status,
                        oier_count = excluded.oier_count,
                        contest_count = excluded.contest_count,
                        school_count = excluded.school_count,
                        record_count = excluded.record_count,
                        github_run_url = excluded.github_run_url,
                        updated_at = CURRENT_TIMESTAMP,
                        activated_at = NULL
                """,
                "params": [
                    release_metadata["source_sha"],
                    release_metadata["data_hash"],
                    release_metadata.get("worker_version"),
                    expected_counts["OIer"],
                    expected_counts["Contest"],
                    expected_counts["School"],
                    expected_counts["Record"],
                    release_metadata.get("run_url"),
                ],
            }
        )
    for table_name, _ in reversed(TABLES):
        statements.append(f"DROP TABLE {table_name}{STAGING_SUFFIX}")

    # Cloudflare D1 batch 是事务：任一语句失败会回滚整批，旧生产数据保持不变。
    execute_d1_batch(cfg, statements)


def upload_database(cfg, release_metadata=None):
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
        promote_staging_tables(cfg, expected_counts, release_metadata)
    finally:
        connection.close()

    print("🎉 全部上传并原子替换完成")


def parse_args():
    parser = argparse.ArgumentParser(description="安全更新 Cloudflare D1 核心数据")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--print-active-sha",
        action="store_true",
        help="打印当前已激活的上游提交 SHA",
    )
    mode.add_argument(
        "--activate-source-sha",
        help="将已完成冒烟测试的上游提交标记为 active",
    )
    parser.add_argument("--source-sha", help="本次数据对应的上游提交 SHA")
    parser.add_argument("--data-hash", help="本次数据构建产物的 SHA-256")
    parser.add_argument("--worker-version", help="本次部署的 Worker 版本")
    parser.add_argument("--run-url", help="触发本次发布的 GitHub Actions 地址")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_config()

    if args.print_active_sha:
        print(get_active_release_sha(cfg))
        return

    if args.activate_source_sha:
        activate_release(cfg, args.activate_source_sha)
        print(f"✅ 已激活数据版本 {args.activate_source_sha}")
        return

    release_metadata = None
    if args.source_sha:
        if not args.data_hash:
            raise ValueError("指定 --source-sha 时必须同时指定 --data-hash")
        release_metadata = {
            "source_sha": args.source_sha,
            "data_hash": args.data_hash,
            "worker_version": args.worker_version,
            "run_url": args.run_url,
        }

    upload_database(cfg, release_metadata)


if __name__ == "__main__":
    main()
