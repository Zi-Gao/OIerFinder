import sqlite3
import json
import os
import tempfile

from cloudflare.script.upstream_data import GENERATOR_DIR, load_encoding_tables

# --- 数据源文件 ---
DIST_DIR = GENERATOR_DIR / 'dist'
STATIC_FILE = DIST_DIR / 'static.json'
RESULT_FILE = DIST_DIR / 'result.txt'

# --- 输出文件 ---
DB_FILE = os.environ.get('OIER_DATABASE_PATH', 'oier_data.db')

def decode_index(value, choices, field, allow_empty=False):
    """解码上游编号；学校的 -1 代表保留 ID 的废弃占位项。"""
    if type(value) is int:
        if allow_empty and value == -1:
            return ''
        if 0 <= value < len(choices):
            return choices[value]
    elif isinstance(value, str):
        if value in choices or (allow_empty and value == ''):
            return value
    raise ValueError(f'Unknown upstream {field}: {value!r}')

def create_tables(cursor):
    """创建数据库表结构"""
    print("Creating tables...")
    # 学校表 (School)
    cursor.execute('''
    CREATE TABLE School (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        province TEXT,
        city TEXT,
        score REAL
    )
    ''')
    # 比赛表 (Contest)
    cursor.execute('''
    CREATE TABLE Contest (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT,
        year INTEGER,
        fall_semester BOOLEAN,
        full_score INTEGER
    )
    ''')
    # 选手表 (OIer)
    cursor.execute('''
    CREATE TABLE OIer (
        uid INTEGER PRIMARY KEY,
        initials TEXT,
        name TEXT NOT NULL,
        gender INTEGER,
        enroll_middle INTEGER,
        oierdb_score REAL,
        ccf_score REAL,
        ccf_level INTEGER
    )
    ''')
    # 记录表 (Record)
    cursor.execute('''
    CREATE TABLE Record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        oier_uid INTEGER,
        contest_id INTEGER,
        school_id INTEGER,
        score REAL,
        rank INTEGER,
        province TEXT,
        level TEXT,
        FOREIGN KEY(oier_uid) REFERENCES OIer(uid),
        FOREIGN KEY(contest_id) REFERENCES Contest(id),
        FOREIGN KEY(school_id) REFERENCES School(id)
    )
    ''')
    print("Tables created successfully.")

def load_static_data(cursor, encodings):
    """从 static.json 加载 School 和 Contest 数据"""
    print("Loading data from static.json...")
    with open(STATIC_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    schools_to_insert = []
    for i, school_data in enumerate(data['schools']):
        province = decode_index(
            school_data[1], encodings['provinces'], 'school province', allow_empty=True
        )
        schools_to_insert.append((i, school_data[0], province, school_data[2], school_data[3]))
    cursor.executemany('INSERT INTO School (id, name, province, city, score) VALUES (?, ?, ?, ?, ?)', schools_to_insert)
    print(f"Inserted {len(schools_to_insert)} schools.")

    contests_to_insert = []
    for i, contest_data in enumerate(data['contests']):
        contests_to_insert.append((
            i, contest_data.get('name'),
            decode_index(contest_data.get('type'), encodings['contest_types'], 'contest type'),
            contest_data.get('year'), contest_data.get('fall_semester'),
            contest_data.get('full_score')
        ))
    cursor.executemany('INSERT INTO Contest (id, name, type, year, fall_semester, full_score) VALUES (?, ?, ?, ?, ?, ?)', contests_to_insert)
    print(f"Inserted {len(contests_to_insert)} contests.")

def load_results_data(cursor, encodings):
    """从 result.txt 加载 OIer 和 Record 数据"""
    print("Loading data from result.txt...")
    oiers_to_insert = []
    records_to_insert = []

    with open(RESULT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',', 8)
            oier_uid = int(parts[0])
            oier_data = (
                oier_uid, parts[1], parts[2], int(parts[3]), int(parts[4]),
                float(parts[5]), float(parts[6]), int(parts[7])
            )
            oiers_to_insert.append(oier_data)

            records_str = parts[8]
            for record_part in records_str.split('/'):
                record_data_str = record_part.split(';')[0].split(':')[0:6]
                score_val = float(record_data_str[2]) if record_data_str[2] else None
                province_idx, level_idx = int(record_data_str[4]), int(record_data_str[5])
                province_str = decode_index(province_idx, encodings['provinces'], 'record province')
                level_str = decode_index(level_idx, encodings['award_levels'], 'award level')
                record_data = (
                    oier_uid, int(record_data_str[0]), int(record_data_str[1]),
                    score_val, int(record_data_str[3]), province_str, level_str
                )
                records_to_insert.append(record_data)

    cursor.executemany('INSERT INTO OIer (uid, initials, name, gender, enroll_middle, oierdb_score, ccf_score, ccf_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', oiers_to_insert)
    print(f"Inserted {len(oiers_to_insert)} OIers.")
    
    cursor.executemany('INSERT INTO Record (oier_uid, contest_id, school_id, score, rank, province, level) VALUES (?, ?, ?, ?, ?, ?, ?)', records_to_insert)
    print(f"Inserted {len(records_to_insert)} Records.")

def validate_database(cursor):
    """在替换现有数据库前验证新数据库完整性。"""
    for table_name in ("School", "Contest", "OIer", "Record"):
        row_count = cursor.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]
        if row_count <= 0:
            raise RuntimeError(
                f"Generated table {table_name} is empty; keeping the existing database."
            )

    foreign_key_errors = cursor.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise RuntimeError(
            f"Generated database has {len(foreign_key_errors)} foreign key errors; "
            "keeping the existing database."
        )

def main():
    """主函数"""
    encodings = load_encoding_tables(GENERATOR_DIR)
    target_path = os.path.abspath(DB_FILE)
    target_dir = os.path.dirname(target_path)
    temp_fd, temp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(DB_FILE)}.",
        suffix=".tmp",
        dir=target_dir,
    )
    os.close(temp_fd)
    conn = None

    try:
        conn = sqlite3.connect(temp_path)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        create_tables(cursor)
        load_static_data(cursor, encodings)
        load_results_data(cursor, encodings)
        validate_database(cursor)
        conn.commit()
        conn.close()
        conn = None
        os.replace(temp_path, target_path)
        print(f"\nDatabase '{DB_FILE}' created and populated successfully!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)

    print(f"\nProcess finished. Check for '{DB_FILE}'.")


if __name__ == '__main__':
    main()
