# generate_stats_json.py
import sqlite3
import json
import argparse
import os
from collections import defaultdict

def generate_stats_json(db_path, output_path):
    """
    连接到 SQLite 数据库，计算统计数据，并生成一个嵌套的 JSON 对象
    用于 Cloudflare Worker。
    """
    if not os.path.exists(db_path):
        print(f"❌ 错误: 数据库文件未找到: '{db_path}'")
        return

    print(f"🔗 正在连接到数据库: {db_path}...")

    sql_query = """
    SELECT
        c.year,
        c.type,
        r.province,
        r.level,
        COUNT(DISTINCT r.oier_uid) as participant_count
    FROM
        Record r
    JOIN
        Contest c ON r.contest_id = c.id
    WHERE
        r.province IS NOT NULL AND r.province != '' AND r.level IS NOT NULL
    GROUP BY
        c.year, c.type, r.province, r.level;
    """

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # 使用 Row 工厂可以让我们通过列名访问数据，更清晰
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("🚀 正在执行统计查询...")
        cursor.execute(sql_query)
        results = cursor.fetchall()

        if not results:
            print("🟡 查询没有返回任何结果。")
            return

        # 构建嵌套字典结构: stats[year][type][province][level] = count
        stats_data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        
        for row in results:
            stats_data[row['year']][row['type']][row['province']][row['level']] = row['participant_count']

        print(f"✍️ 正在将统计数据写入到 JSON 文件: {output_path}...")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)

        print("\n✅ JSON 统计文件生成成功！")
        print("💡 下一步：复制 "
              f"'{output_path}' 文件的全部内容，然后粘贴到你的 Cloudflare Worker JS 代码中。")

    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
    finally:
        if conn:
            conn.close()
            print("🔗 数据库连接已关闭。")

def main():
    parser = argparse.ArgumentParser(description="为 OIer 查询 Worker 生成统计数据 JSON。")
    parser.add_argument("--db", default="oier_data.db", help="SQLite 数据库文件路径")
    parser.add_argument("--output", default="contest_stats.json", help="输出的 JSON 文件路径")
    args = parser.parse_args()
    generate_stats_json(args.db, args.output)

if __name__ == "__main__":
    main()