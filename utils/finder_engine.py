# finder_engine.py
import sqlite3
from datetime import date

ENUMERATE_THRESHOLD = 20

def build_where_clause_and_values(params):
    # ... (这个函数和 oierfinder.py 中的完全一样) ...
    conditions, values = [], []
    range_fields = {'year_range': 'c.year', 'score_range': 'r.score', 'rank_range': 'r.rank'}
    list_fields = {'province': 'r.province', 'level_range': 'r.level', 'contest_type': 'c.type'}
    for field, column in range_fields.items():
        if field in params and params[field]:
            min_val, max_val = params[field]
            if min_val is not None: conditions.append(f"{column} >= ?"); values.append(min_val)
            if max_val is not None: conditions.append(f"{column} <= ?"); values.append(max_val)
    for field, column in list_fields.items():
        if field in params and params[field] and params[field][0] is not None:
             placeholders = ', '.join(['?'] * len(params[field])); conditions.append(f"{column} IN ({placeholders})"); values.extend(params[field])
    return " AND ".join(conditions) if conditions else "1=1", values

def find_oiers(config, cursor):
    # ... (这个函数也和 oierfinder.py 中的几乎一样) ...
    # 唯一的区别是，它只接受 config 和 cursor，并返回结果列表
    if not config: config = {}

    initial_candidates = None
    oier_conditions, oier_values = [], []

    if config.get('enroll_year_range') and any(v is not None for v in config['enroll_year_range']):
        min_yr, max_yr = config['enroll_year_range']
        if min_yr is not None: oier_conditions.append("enroll_middle >= ?"); oier_values.append(min_yr)
        if max_yr is not None: oier_conditions.append("enroll_middle <= ?"); oier_values.append(max_yr)
            
    if config.get('grade_range') and any(v is not None for v in config['grade_range']):
        min_grade, max_grade = config['grade_range']
        current_year = date.today().year
        if max_grade is not None: oier_conditions.append("enroll_middle >= ?"); oier_values.append(current_year - max_grade + 7)
        if min_grade is not None: oier_conditions.append("enroll_middle <= ?"); oier_values.append(current_year - min_grade + 7)

    if oier_conditions:
        where_clause = " AND ".join(oier_conditions)
        query = f"SELECT uid FROM OIer WHERE {where_clause}"
        cursor.execute(query, oier_values)
        initial_candidates = {row[0] for row in cursor.fetchall()}
    
    candidate_uids = initial_candidates
    record_constraints = config.get('records', [])
    enumeration_mode = bool(candidate_uids and len(candidate_uids) < ENUMERATE_THRESHOLD)
    
    for constraint in record_constraints:
        where_clause, values = build_where_clause_and_values(constraint)
        if enumeration_mode and candidate_uids:
            placeholders = ', '.join(['?'] * len(candidate_uids))
            where_clause += f" AND r.oier_uid IN ({placeholders})"
            values.extend(list(candidate_uids))
        query = f"SELECT DISTINCT r.oier_uid FROM Record r JOIN Contest c ON r.contest_id = c.id WHERE {where_clause}"
        cursor.execute(query, values)
        uids_for_this_constraint = {row[0] for row in cursor.fetchall()}
        if candidate_uids is None: candidate_uids = uids_for_this_constraint
        else: candidate_uids.intersection_update(uids_for_this_constraint)
        if not enumeration_mode and candidate_uids and len(candidate_uids) < ENUMERATE_THRESHOLD: enumeration_mode = True
        if not candidate_uids: break

    if candidate_uids is None:
        if not oier_conditions and not record_constraints:
            cursor.execute("SELECT * FROM OIer ORDER BY oierdb_score DESC")
        else: return []
    elif not candidate_uids: return []
    else:
        placeholders = ', '.join(['?'] * len(candidate_uids))
        query = f"SELECT * FROM OIer WHERE uid IN ({placeholders}) ORDER BY oierdb_score DESC"
        cursor.execute(query, list(candidate_uids))
    return cursor.fetchall()