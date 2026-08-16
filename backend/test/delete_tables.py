# delete_tables.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "../agent_platform.db")


def delete_tables(table_names):
    """删除指定的表"""
    if not os.path.exists(DB_PATH):
        print(f"数据库文件不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 查看当前所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = [t[0] for t in cursor.fetchall()]
    print(f"当前表: {all_tables}")

    # 删除指定表
    for table in table_names:
        if table in all_tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"✓ 已删除表: {table}")
        else:
            print(f"- 表不存在，跳过: {table}")

    conn.commit()
    conn.close()
    print("完成")


if __name__ == "__main__":
    # 删除 models 相关表，重启后会自动重建
    delete_tables(["models", "model_providers"])
