"""Hermes Agent 迁移 - 替换 OpenClaw

Revision ID: hermes_001
Revises: 045d563e7600
Create Date: 2024-01-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "hermes_001"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 删除旧 OpenClaw 表
    op.drop_table("openclaw_messages")
    op.drop_table("openclaw_runs")
    op.drop_table("openclaw_sessions")

    # 创建新 Hermes 表
    op.create_table(
        "hermes_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), server_default="新会话"),
        sa.Column("model", sa.String(100), server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hermes_sessions_user_id", "hermes_sessions", ["user_id"])

    op.create_table(
        "hermes_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("hermes_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), server_default=""),
        sa.Column("tools_used", sa.JSON(), server_default="[]"),
        sa.Column("token_input", sa.Integer(), server_default="0"),
        sa.Column("token_output", sa.Integer(), server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hermes_messages_session_id", "hermes_messages", ["session_id"])

    op.create_table(
        "hermes_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("hermes_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("tools_used", sa.JSON(), server_default="[]"),
        sa.Column("token_input", sa.Integer(), server_default="0"),
        sa.Column("token_output", sa.Integer(), server_default="0"),
        sa.Column("latency_ms", sa.Float(), server_default="0.0"),
        sa.Column("error_message", sa.Text(), server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hermes_runs_session_id", "hermes_runs", ["session_id"])


def downgrade() -> None:
    # 删除新 Hermes 表
    op.drop_index("ix_hermes_runs_session_id", table_name="hermes_runs")
    op.drop_table("hermes_runs")
    op.drop_index("ix_hermes_messages_session_id", table_name="hermes_messages")
    op.drop_table("hermes_messages")
    op.drop_index("ix_hermes_sessions_user_id", table_name="hermes_sessions")
    op.drop_table("hermes_sessions")

    # 恢复旧 OpenClaw 表
    op.create_table(
        "openclaw_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent_id", sa.String(50), server_default="main"),
        sa.Column("title", sa.String(255), server_default="新会话"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),
    )

    op.create_table(
        "openclaw_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("openclaw_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("response_id", sa.String(255), nullable=True),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),
    )

    op.create_table(
        "openclaw_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("openclaw_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("response_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="created"),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),
    )
