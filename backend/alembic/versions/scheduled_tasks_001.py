"""
移动端定时任务与推送设备

Revision ID: scheduled_tasks_001
Revises: hermes_attachments_prompts_001
Create Date: 2026-09-07 00:00:00.000000

内容：
1. scheduled_tasks      定时任务定义（含 locked_at 乐观锁）
2. scheduled_task_runs  执行历史
3. device_push_tokens   移动端 Expo Push 令牌

注意：本项目开发期靠 Base.metadata.create_all() 自动建表，因此本迁移
对"表已存在"做了幂等处理，避免重复创建报错。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "scheduled_tasks_001"
down_revision: str | None = "hermes_attachments_prompts_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in inspector.get_table_names()


def upgrade() -> None:
    # 1. 定时任务
    if not _has_table("scheduled_tasks"):
        op.create_table(
            "scheduled_tasks",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=True),
            sa.Column("app_id", sa.String(), nullable=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("schedule_type", sa.String(length=20), nullable=False),
            sa.Column("cron_expr", sa.String(length=100), nullable=True),
            sa.Column("run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("timezone", sa.String(length=64), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("deliver_push", sa.Boolean(), nullable=False),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_status", sa.String(length=20), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("fail_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(
                ["session_id"], ["hermes_sessions.id"], ondelete="SET NULL"
            ),
        )
        op.create_index("ix_scheduled_tasks_user_id", "scheduled_tasks", ["user_id"])
        op.create_index(
            "ix_scheduled_tasks_next_run_at", "scheduled_tasks", ["next_run_at"]
        )

    # 2. 执行历史
    if not _has_table("scheduled_task_runs"):
        op.create_table(
            "scheduled_task_runs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("task_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("session_id", sa.String(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["task_id"], ["scheduled_tasks.id"], ondelete="CASCADE"
            ),
        )
        op.create_index(
            "ix_scheduled_task_runs_task_id", "scheduled_task_runs", ["task_id"]
        )

    # 3. 推送设备令牌
    if not _has_table("device_push_tokens"):
        op.create_table(
            "device_push_tokens",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token", sa.String(length=255), nullable=False),
            sa.Column("platform", sa.String(length=20), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.UniqueConstraint("token"),
        )
        op.create_index(
            "ix_device_push_tokens_user_id", "device_push_tokens", ["user_id"]
        )
        op.create_index(
            "ix_device_push_tokens_token", "device_push_tokens", ["token"], unique=True
        )


def downgrade() -> None:
    if _has_table("device_push_tokens"):
        op.drop_table("device_push_tokens")
    if _has_table("scheduled_task_runs"):
        op.drop_table("scheduled_task_runs")
    if _has_table("scheduled_tasks"):
        op.drop_table("scheduled_tasks")
