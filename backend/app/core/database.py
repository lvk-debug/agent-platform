from datetime import UTC

from sqlalchemy import DateTime, TypeDecorator, create_engine, event, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# 根据数据库类型创建引擎
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite配置: WAL模式 + busy_timeout 解决并发死锁
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=settings.DEBUG,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
else:
    # PostgreSQL配置
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=settings.DEBUG,
    )

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


class UTCDateTime(TypeDecorator):
    """
    读写两端都保证 UTC aware 的 DateTime

    SQLite 不保存时区：`DateTime(timezone=True)` 写入后读回会变成 **naive**，
    由此引发两类问题：

    1. 与 `datetime.now(UTC)` 相减直接抛
       `can't subtract offset-naive and offset-aware datetimes`；
    2. naive 值序列化成 ISO 后没有时区后缀，前端会当**本地时间**解析，偏差一个时区。

    这里在驱动层统一补齐。最初定义在 models/learning.py 内，提取为公共类型供新模块复用。
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN201
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    def process_result_value(self, value, dialect):  # noqa: ANN201
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)


# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 旧库结构补齐（create_all 不会为已存在的表新增列，这里做幂等补充）
_LIGHT_MIGRATIONS = {
    "hermes_sessions": {"skills": "JSON", "tools": "JSON"},
    "hermes_runs": {"external_run_id": "VARCHAR(100)"},
    # 学习助手 AI 问答：create_all 不会给已存在的表补列，旧库需显式迁移。
    # index_status / index_chunk_count 在 ORM 上是非空列，故这里必须给默认值，
    # 否则 SQLite 的 ALTER TABLE ADD COLUMN NOT NULL 会因无默认值而失败。
    "learning_resources": {
        "summary": "TEXT",
        "index_status": "VARCHAR(20) DEFAULT 'pending'",
        "index_error": "TEXT",
        "index_chunk_count": "INTEGER DEFAULT 0",
        "suggested_questions": "JSON",
        "suggested_questions_at": "DATETIME",
    },
    # 客服多 Agent：SupportMessage.trace 持久化 Agent 处理过程，旧库补列兜底。
    "support_messages": {
        "trace": "JSON",
    },
    # 客服评测：自动评测由自研四维度裁判改为 DeepEval，新增 deepeval_* 结果列。
    "support_evaluations": {
        "deepeval_scores": "JSON",
        "deepeval_overall": "FLOAT",
        "deepeval_reasoning": "TEXT",
    },
}


def ensure_light_migrations() -> None:
    """为已有的旧表补充新增列，失败仅记录日志，不阻断启动"""
    from app.utils.logger import logger

    inspector = inspect(engine)
    try:
        with engine.begin() as conn:
            for table, columns in _LIGHT_MIGRATIONS.items():
                if not inspector.has_table(table):
                    continue
                existing = {col["name"] for col in inspector.get_columns(table)}
                for name, ddl in columns.items():
                    if name not in existing:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                        logger.info(f"已为 {table} 补充列 {name}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"轻量结构补齐失败（可忽略，建议执行 alembic upgrade head）: {e}")
