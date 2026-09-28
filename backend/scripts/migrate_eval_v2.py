"""
评估系统 v2 迁移脚本

删除旧的评估相关表，重新创建新表结构。
适用于 SQLite 开发环境。
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import engine, SessionLocal
from app.core.database import Base

# 导入所有模型以注册到 Base.metadata
from app.models import *  # noqa: F401, F403


def migrate():
    """执行迁移"""
    print("[START] Evaluation system v2 migration...")

    # 需要删除的表（按外键依赖顺序）
    tables_to_drop = [
        "evaluation_results",
        "traces",
        "evaluations",
        "test_cases",
        "evaluators",
        "evaluation_datasets",
    ]

    with engine.begin() as conn:
        for table in tables_to_drop:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                print(f"  [OK] Dropped table: {table}")
            except Exception as e:
                print(f"  [FAIL] Drop table {table}: {e}")

    # 重新创建所有表
    print("\nRecreating tables...")
    Base.metadata.create_all(bind=engine)
    print("  [OK] All tables created")

    # 验证新表
    print("\nVerifying tables:")
    with engine.connect() as conn:
        if engine.url.drivername == "sqlite":
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
        else:
            result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        for row in result:
            print(f"  - {row[0]}")

    print("\n[DONE] Migration completed!")


if __name__ == "__main__":
    migrate()
