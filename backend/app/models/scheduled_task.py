"""
定时任务数据模型

两张表（UUID 主键，时间戳统一 UTC）：
- scheduled_tasks      定时任务定义
- scheduled_task_runs  每次执行的运行记录

设计要点：
1. **枚举用普通字符串常量**：SQLite 的 Enum 以 VARCHAR + CHECK 实现，新增枚举值
   必须走 Alembic 迁移；这里改用模块级常量 + 服务层校验，避免迁移负担。
2. **locked_at 做 CAS 乐观锁**：多进程/多 worker 同时触发时，只有成功把
   locked_at 从「空或过期」改成当前时间的那个进程能真正执行，防止重复执行。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ScheduleType:
    """调度类型"""

    ONCE = "once"  # 单次，按 run_at 执行
    DAILY = "daily"  # 每天固定时间
    WEEKLY = "weekly"  # 每周固定星期+时间
    CRON = "cron"  # 自定义 crontab 表达式

    ALL = (ONCE, DAILY, WEEKLY, CRON)


class RunStatus:
    """执行状态"""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

    ALL = (RUNNING, SUCCESS, FAILED)


class ScheduledTask(Base):
    """定时任务"""

    __tablename__ = "scheduled_tasks"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 执行目标：优先 session_id（Hermes 会话），为空则按 app_id 走应用对话
    session_id = Column(
        String, ForeignKey("hermes_sessions.id", ondelete="SET NULL"), nullable=True
    )
    app_id = Column(String, nullable=True)

    name = Column(String(100), nullable=False, default="未命名任务")
    prompt = Column(Text, nullable=False, default="")

    schedule_type = Column(String(20), nullable=False, default=ScheduleType.DAILY)
    cron_expr = Column(String(100), nullable=True)  # schedule_type=cron 时必填
    run_at = Column(DateTime(timezone=True), nullable=True)  # schedule_type=once 时必填
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai")

    enabled = Column(Boolean, nullable=False, default=True)
    deliver_push = Column(Boolean, nullable=False, default=True)

    # 调度与执行状态
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)  # CAS 乐观锁

    last_status = Column(String(20), nullable=True)
    last_error = Column(Text, nullable=True)
    fail_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<ScheduledTask(id={self.id}, name={self.name}, "
            f"type={self.schedule_type}, enabled={self.enabled})>"
        )


class ScheduledTaskRun(Base):
    """定时任务执行记录"""

    __tablename__ = "scheduled_task_runs"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(
        String,
        ForeignKey("scheduled_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = Column(String(20), nullable=False, default=RunStatus.RUNNING)
    summary = Column(Text, nullable=True)  # 结果摘要（推送正文）
    error = Column(Text, nullable=True)
    session_id = Column(String, nullable=True)  # 本次实际写入的会话

    started_at = Column(DateTime(timezone=True), default=_utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"<ScheduledTaskRun(id={self.id}, task={self.task_id}, "
            f"status={self.status})>"
        )
