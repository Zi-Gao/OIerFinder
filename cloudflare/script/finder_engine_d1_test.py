import requests
import yaml
import json
from datetime import date

# 配置文件路径
CONFIG_FILE = "config.yml"

# 阈值（保持与原代码一致）
ENUMERATE_THRESHOLD = 20

# 统计变量
query_count = 0
total_rows_returned = 0
DEBUG_SQL = True  # 设置 False 可关闭 SQL 输出

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def execute_d1_sql(cfg, sql, params=None):
    """
    调用 Cloudflare D1 raw SQL API 执行查询，并统计用量，返回行字典列表
    """
    global query_count, total_rows_returned
    if params is None:
        params = []

    # 替换 ? 占位符（仅测试用途）
    safe_sql = sql
    for p in params:
        if p is None:
            val_str = "NULL"
        elif isinstance(p, str):
            val_str = "'" + p.replace("'", "''") + "'"
        else:
            val_str = str(p)
        safe_sql = safe_sql.replace("?", val_str, 1)

    if DEBUG_SQL:
        print(f"\n[Query #{query_count+1}] {safe_sql}")

    url = f"https://api.cloudflare.com/client/v4/accounts/{cfg['cloudflare']['account_id']}/d1/database/{cfg['cloudflare']['database_id']}/raw"
    headers = {
        "Authorization": f"Bearer {cfg['cloudflare']['api_token']}",
        "Content-Type": "application/json",
    }
    payload = {"sql": safe_sql}

    resp = requests.post(url, headers=headers, data=json.dumps(payload))
    query_count += 1

    if resp.status_code != 200:
        print(f"❌ 请求失败: HTTP {resp.status_code}")
        print(resp.text)
        return []

    data = resp.json()
    if not isinstance(data, list):
        print(f"⚠️ API 返回不是数组格式: {data}")
        return []

    # 新版 D1 返回是一个数组，每个元素对应一次 SQL 结果
    first_result = data[0]
    if not first_result.get("success", False):
        print(f"❌ SQL 执行错误: {first_result}")
        return []

    results_data = first_result.get("results", {})
    columns = results_data.get("columns", [])
    rows_data = results_data.get("rows", [])

    # 转字典
    rows = [dict(zip(columns, row)) for row in rows_data]

    total_rows_returned += len(rows)
    if DEBUG_SQL:
        print(f"→ 返回 {len(rows)} 行")
    return rows

def build_where_clause_and_values(params):
    conditions, values = [], []
    range_fields = {
        "year_range": "c.year",
        "score_range": "r.score",
        "rank_range": "r.rank",
    }
    list_fields = {
        "province": "r.province",
        "level_range": "r.level",
        "contest_type": "c.type",
    }
    for field, column in range_fields.items():
        if field in params and params[field]:
            min_val, max_val = params[field]
            if min_val is not None:
                conditions.append(f"{column} >= ?")
                values.append(min_val)
            if max_val is not None:
                conditions.append(f"{column} <= ?")
                values.append(max_val)
    for field, column in list_fields.items():
        if field in params and params[field] and params[field][0] is not None:
            placeholders = ", ".join(["?"] * len(params[field]))
            conditions.append(f"{column} IN ({placeholders})")
            values.extend(params[field])
    return " AND ".join(conditions) if conditions else "1=1", values

def find_oiers(cfg, config):
    global query_count, total_rows_returned
    query_count = 0
    total_rows_returned = 0

    if not config:
        config = {}
    initial_candidates = None
    oier_conditions, oier_values = [], []

    # enroll_year_range 过滤
    if config.get("enroll_year_range") and any(v is not None for v in config["enroll_year_range"]):
        min_yr, max_yr = config["enroll_year_range"]
        if min_yr is not None:
            oier_conditions.append("enroll_middle >= ?")
            oier_values.append(min_yr)
        if max_yr is not None:
            oier_conditions.append("enroll_middle <= ?")
            oier_values.append(max_yr)
    # grade_range 过滤
    if config.get("grade_range") and any(v is not None for v in config["grade_range"]):
        min_grade, max_grade = config["grade_range"]
        current_year = date.today().year
        if max_grade is not None:
            oier_conditions.append("enroll_middle >= ?")
            oier_values.append(current_year - max_grade + 7)
        if min_grade is not None:
            oier_conditions.append("enroll_middle <= ?")
            oier_values.append(current_year - min_grade + 7)

    if oier_conditions:
        where_clause = " AND ".join(oier_conditions)
        query = f"SELECT uid FROM OIer WHERE {where_clause}"
        rows = execute_d1_sql(cfg, query, oier_values)
        initial_candidates = {row["uid"] for row in rows}

    candidate_uids = initial_candidates
    record_constraints = config.get("records", [])
    enumeration_mode = bool(candidate_uids and len(candidate_uids) < ENUMERATE_THRESHOLD)

    # 遍历每个 Record 条件
    for constraint in record_constraints:
        where_clause, values = build_where_clause_and_values(constraint)
        if enumeration_mode and candidate_uids:
            placeholders = ", ".join(["?"] * len(candidate_uids))
            where_clause += f" AND r.oier_uid IN ({placeholders})"
            values.extend(list(candidate_uids))
        query = f"""
            SELECT DISTINCT r.oier_uid
            FROM Record r
            JOIN Contest c ON r.contest_id = c.id
            WHERE {where_clause}
        """
        rows = execute_d1_sql(cfg, query, values)
        uids_for_this_constraint = {row["oier_uid"] for row in rows}
        if candidate_uids is None:
            candidate_uids = uids_for_this_constraint
        else:
            candidate_uids.intersection_update(uids_for_this_constraint)
        if not enumeration_mode and candidate_uids and len(candidate_uids) < ENUMERATE_THRESHOLD:
            enumeration_mode = True
        if not candidate_uids:
            break

    # 最终取 OIer 详情
    if candidate_uids is None:
        if not oier_conditions and not record_constraints:
            execute_d1_sql(cfg, "SELECT * FROM OIer ORDER BY oierdb_score DESC")
        else:
            return []
    elif not candidate_uids:
        return []
    else:
        placeholders = ", ".join(["?"] * len(candidate_uids))
        query = f"SELECT * FROM OIer WHERE uid IN ({placeholders}) ORDER BY oierdb_score DESC"
        execute_d1_sql(cfg, query, list(candidate_uids))

    print("\n📊 云端测试结果")
    print(f"🔢 SQL 查询次数（D1 Request 次数）: {query_count}")
    print(f"📦 总返回行数: {total_rows_returned}")
    return []

if __name__ == "__main__":
    cfg = load_config()

    # 示例 config（可以改成你测试的条件）
    test_config = {
        "enroll_year_range": (2019, 2019),
        "records": [
            {"year_range": (2022, 2022), "province": ["北京"]},
            {"contest_type": ["NOI"]}
        ]
    }

    find_oiers(cfg, test_config)