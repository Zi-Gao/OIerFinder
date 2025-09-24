# generate_stats_json.py
import sqlite3
import json
import argparse
import os
from collections import defaultdict

def generate_stats_json(db_path, output_path):
    """
    连接到 SQLite 数据库，计算统计数据，并生成一个包含全局年份范围和
    详细统计数据的嵌套 JSON 对象，用于 Cloudflare Worker。
    """
    if not os.path.exists(db_path):
        print(f"❌ 错误: 数据库文件未找到: '{db_path}'")
        return

    print(f"🔗 正在连接到数据库: {db_path}...")

    # 用于计算每个比赛/省份/奖项组合的人数
    stats_query = """
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
    
    # 用于获取全局的最小和最大年份
    year_range_query = "SELECT MIN(year), MAX(year) FROM Contest;"

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # 使用 Row 工厂方便按列名访问
        cursor = conn.cursor()

        # 1. 获取年份范围
        print("🔍 正在查询全局年份范围...")
        cursor.execute(year_range_query)
        year_row = cursor.fetchone()
        min_year, max_year = (year_row[0], year_row[1]) if year_row else (None, None)
        
        if min_year is None:
            print("🟡 警告: Contest 表中没有数据，无法确定年份范围。")
            return

        print(f"📅 全局年份范围: {min_year} - {max_year}")

        # 2. 获取详细统计数据
        print("🚀 正在执行详细统计查询...")
        cursor.execute(stats_query)
        results = cursor.fetchall()

        if not results:
            print("🟡 查询没有返回任何统计结果。")
            return

        # 构建嵌套字典结构: stats[year][type][province][level] = count
        stats_data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        for row in results:
            stats_data[row['year']][row['type']][row['province']][row['level']] = row['participant_count']

        # 3. 组合最终的 JSON 对象
        final_json_output = {
            "min_year": min_year,
            "max_year": max_year,
            "stats": stats_data
        }

        print(f"✍️ 正在将 {len(results)} 条统计结果和年份范围写入到 JSON 文件: {output_path}...")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # indent=None 可以生成更紧凑的单行 JSON，减小 Worker 文件体积
            json.dump(final_json_output, f, ensure_ascii=False)

        print("\n✅ JSON 统计文件生成成功！")
        print(f"💡 下一步：将 '{output_path}' 文件放到你的 Worker 项目目录下，并确保构建工具能处理 JSON 导入。")

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