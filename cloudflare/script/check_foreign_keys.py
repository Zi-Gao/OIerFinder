import sqlite3
import os
import sys
from tabulate import tabulate

def check_foreign_keys(db_path):
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查具体缺失的外键情况
    query = """
    SELECT r.id, r.oier_uid, r.contest_id, r.school_id,
           CASE WHEN o.uid IS NULL THEN '缺少 OIer' ELSE '' END AS missing_oier,
           CASE WHEN c.id IS NULL THEN '缺少 Contest' ELSE '' END AS missing_contest,
           CASE WHEN s.id IS NULL THEN '缺少 School' ELSE '' END AS missing_school
    FROM Record r
    LEFT JOIN OIer o ON r.oier_uid = o.uid
    LEFT JOIN Contest c ON r.contest_id = c.id
    LEFT JOIN School s ON r.school_id = s.id
    WHERE o.uid IS NULL OR c.id IS NULL OR s.id IS NULL
    LIMIT 100;   -- 限制结果，防止一次性输出太多
    """

    cursor.execute("""
    SELECT COUNT(*)
    FROM Record r
    LEFT JOIN OIer o ON r.oier_uid = o.uid
    LEFT JOIN Contest c ON r.contest_id = c.id
    LEFT JOIN School s ON r.school_id = s.id
    WHERE o.uid IS NULL OR c.id IS NULL OR s.id IS NULL
    """)
    total_bad = cursor.fetchone()[0]

    print(f"🔍 检查结果：共有 {total_bad} 条 Record 外键不一致")

    if total_bad > 0:
        print("显示前 100 条问题记录：")
        cursor.execute(query)
        rows = cursor.fetchall()
        headers = ["Record.id", "oier_uid", "contest_id", "school_id",
                   "缺失OIer", "缺失Contest", "缺失School"]
        print(tabulate(rows, headers=headers, tablefmt="grid"))

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_foreign_keys.py <sqlite数据库路径>")
        sys.exit(1)

    db_file = sys.argv[1]
    check_foreign_keys(db_file)