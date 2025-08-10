import sqlite3
import os

# --- 数据库文件 ---
DB_FILE = 'oier_data.db'

def run_tests(cursor):
    """在数据库上运行一系列测试"""
    print("\n--- Running Tests ---")
    all_tests_passed = True

    # 测试 1: 检查各表行数
    print("\n[Test 1: Row Counts]")
    tables = ["School", "Contest", "OIer", "Record"]
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"  - SUCCESS: Table '{table}' contains {count} rows.")
            else:
                print(f"  - FAILURE: Table '{table}' is empty.")
                all_tests_passed = False
        except sqlite3.Error as e:
            print(f"  - FAILURE: Could not query table '{table}': {e}")
            all_tests_passed = False
            
    if not all_tests_passed:
        return False

    # 测试 2: 随机获取一个 OIer 并验证其数据
    print("\n[Test 2: Fetch a specific OIer]")
    test_uid = None
    try:
        cursor.execute("SELECT * FROM OIer ORDER BY RANDOM() LIMIT 1")
        oier = cursor.fetchone()
        if oier:
            test_uid = oier[0]
            print(f"  - SUCCESS: Fetched random OIer: UID={test_uid}, Name={oier[2]}, Score={oier[5]:.2f}")
        else:
            print("  - FAILURE: Could not fetch a random OIer.")
            all_tests_passed = False
    except sqlite3.Error as e:
        print(f"  - FAILURE: Could not query OIer table: {e}")
        all_tests_passed = False

    if not test_uid:
        return all_tests_passed
        
    # 测试 3: 验证外键关系 (JOIN查询)
    print(f"\n[Test 3: JOIN Query for OIer UID {test_uid}]")
    try:
        query = """
        SELECT
            r.id, o.name, s.name, c.name, r.score, r.rank
        FROM Record r
        JOIN OIer o ON r.oier_uid = o.uid
        JOIN School s ON r.school_id = s.id
        JOIN Contest c ON r.contest_id = c.id
        WHERE o.uid = ?
        ORDER BY c.year DESC
        LIMIT 5
        """
        cursor.execute(query, (test_uid,))
        records = cursor.fetchall()
        if records:
            print(f"  - SUCCESS: Found {len(records)} records for OIer '{records[0][1]}'.")
            print("    Sample record:")
            sample = records[0]
            print(f"      Record ID: {sample[0]}, OIer: {sample[1]}, School: {sample[2]}, Contest: {sample[3]}")
        else:
            print(f"  - INFO: No records found for OIer UID {test_uid} via JOIN, which might be valid.")
    except sqlite3.Error as e:
        print(f"  - FAILURE: JOIN query failed: {e}")
        all_tests_passed = False
        
    return all_tests_passed

def main():
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' not found.")
        print("Please run create_db.py first.")
        return

    conn = None
    try:
        # 直接连接到数据库文件
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        if run_tests(cursor):
            print("\n--- All tests passed successfully! ---")
        else:
            print("\n--- Some tests failed. Please review the output. ---")
            
    except Exception as e:
        print(f"\nAn unexpected error occurred during testing: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    main()