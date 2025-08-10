import sqlite3
import json
import os

# --- 数据源文件 ---
DIST_DIR = 'oierdb-data/dist'
STATIC_FILE = os.path.join(DIST_DIR, 'static.json')
RESULT_FILE = os.path.join(DIST_DIR, 'result.txt')

# --- 输出文件 ---
DB_FILE = 'oier_data.db'

# 从 util.py 中复制，用于解码索引
PROVINCES = [
    "安徽", "北京", "福建", "甘肃", "广东", "广西", "贵州", "海南", "河北", "河南",
    "黑龙江", "湖北", "湖南", "吉林", "江苏", "江西", "辽宁", "内蒙古", "山东", "山西",
    "陕西", "上海", "四川", "天津", "新疆", "浙江", "重庆", "宁夏", "云南", "澳门",
    "香港", "青海", "西藏", "台湾",
]
AWARD_LEVELS = [
    "金牌", "银牌", "铜牌", "一等奖", "二等奖", "三等奖", "国际金牌", "国际银牌",
    "国际铜牌", "前5%", "前15%", "前25%",
]

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

def load_static_data(cursor):
    """从 static.json 加载 School 和 Contest 数据"""
    print("Loading data from static.json...")
    with open(STATIC_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    schools_to_insert = []
    for i, school_data in enumerate(data['schools']):
        schools_to_insert.append((i, school_data[0], school_data[1], school_data[2], school_data[3]))
    cursor.executemany('INSERT INTO School (id, name, province, city, score) VALUES (?, ?, ?, ?, ?)', schools_to_insert)
    print(f"Inserted {len(schools_to_insert)} schools.")

    contests_to_insert = []
    for i, contest_data in enumerate(data['contests']):
        contests_to_insert.append((
            i, contest_data.get('name'), contest_data.get('type'),
            contest_data.get('year'), contest_data.get('fall_semester'),
            contest_data.get('full_score')
        ))
    cursor.executemany('INSERT INTO Contest (id, name, type, year, fall_semester, full_score) VALUES (?, ?, ?, ?, ?, ?)', contests_to_insert)
    print(f"Inserted {len(contests_to_insert)} contests.")

def load_results_data(cursor):
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
                province_str = PROVINCES[province_idx] if 0 <= province_idx < len(PROVINCES) else record_data_str[4]
                level_str = AWARD_LEVELS[level_idx] if 0 <= level_idx < len(AWARD_LEVELS) else record_data_str[5]
                record_data = (
                    oier_uid, int(record_data_str[0]), int(record_data_str[1]),
                    score_val, int(record_data_str[3]), province_str, level_str
                )
                records_to_insert.append(record_data)

    cursor.executemany('INSERT INTO OIer (uid, initials, name, gender, enroll_middle, oierdb_score, ccf_score, ccf_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', oiers_to_insert)
    print(f"Inserted {len(oiers_to_insert)} OIers.")
    
    cursor.executemany('INSERT INTO Record (oier_uid, contest_id, school_id, score, rank, province, level) VALUES (?, ?, ?, ?, ?, ?, ?)', records_to_insert)
    print(f"Inserted {len(records_to_insert)} Records.")

def main():
    """主函数"""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        create_tables(cursor)
        load_static_data(cursor)
        load_results_data(cursor)
        conn.commit()
        print(f"\nDatabase '{DB_FILE}' created and populated successfully!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

    print(f"\nProcess finished. Check for '{DB_FILE}'.")


if __name__ == '__main__':
    main()