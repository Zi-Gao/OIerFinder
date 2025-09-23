# calculate_stats.py
import sqlite3
import json
from pathlib import Path

def calculate_and_save_stats():
    """
    连接到oier_data.db，计算筛选条件的组合统计数据，并保存为JSON。
    """
    db_path = Path(__file__).parent / 'oier_data.db'
    output_path = Path(__file__).parent / 'filter_stats.json'
    
    if not db_path.exists():
        print(f"❌ 错误: 数据库文件 'oier_data.db' 未在脚本目录中找到。")
        return

    print(f"🔗 正在连接数据库: {db_path}...")
    
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        
        # 这个查询是核心：按年、比赛类型、省份、奖项级别分组，
        # 计算每个组里有多少个不同的选手。
        sql_query = """
        SELECT
            c.year,
            c.type,
            r.province,
            r.level,
            COUNT(DISTINCT r.oier_uid) as oier_count
        FROM Record r
        JOIN Contest c ON r.contest_id = c.id
        WHERE 
            r.province IS NOT NULL AND r.province != '' AND
            r.level IS NOT NULL
        GROUP BY
            c.year,
            c.type,
            r.province,
            r.level;
        """
        
        print("📊 正在计算统计数据，这可能需要一些时间...")
        cur.execute(sql_query)
        rows = cur.fetchall()
        
        stats = {}
        # 我们使用 "year_type_province_level" 作为key，方便在JS中快速查找
        for year, contest_type, province, level, count in rows:
            key = f"{year}_{contest_type}_{province}_{level}"
            stats[key] = count
            
        print(f"✅ 计算完成，共生成 {len(stats)} 条统计记录。")
        
        # 将统计数据写入JSON文件
        print(f"💾 正在将数据写入: {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f,ensure_ascii=False) # 不加indent，减小文件体积
        
        print("🎉 成功生成 filter_stats.json!")

    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
    finally:
        if 'con' in locals() and con:
            con.close()
            print("🔗 数据库连接已关闭。")

if __name__ == "__main__":
    calculate_and_save_stats()
