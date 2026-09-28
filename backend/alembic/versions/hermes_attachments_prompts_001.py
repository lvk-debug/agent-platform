"""Hermes 附件与快捷提示词

Revision ID: hermes_attachments_prompts_001
Revises: hermes_capability_001
Create Date: 2026-09-07 00:00:00.000000

内容：
1. 新建 hermes_attachments 表（会话附件：图片走视觉通道 / 文档解析注入）
2. 新建 hermes_quick_prompts 表（快捷提示词：内置 + 用户自建）

注意：本项目开发期靠 Base.metadata.create_all() 自动建表，因此本迁移
对"表已存在"做了幂等处理，避免重复创建报错。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "hermes_attachments_prompts_001"
down_revision: Union[str, None] = "hermes_capability_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    """判断表是否已存在（兼容 create_all 已先行建表的环境）"""
    inspector = sa.inspect(op.get_bind())
    return name in inspector.get_table_names()


def upgrade() -> None:
    # 1. 会话附件
    if not _has_table("hermes_attachments"):
        op.create_table(
            "hermes_attachments",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=True),
            sa.Column("message_id", sa.String(), nullable=True),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("stored_name", sa.String(length=255), nullable=False),
            sa.Column("file_path", sa.String(length=500), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("parse_status", sa.String(length=20), nullable=True),
            sa.Column("parsed_text", sa.Text(), nullable=True),
            sa.Column("parse_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["message_id"], ["hermes_messages.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["session_id"], ["hermes_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for idx, col in (
        ("ix_hermes_attachments_user_id", "user_id"),
        ("ix_hermes_attachments_session_id", "session_id"),
        ("ix_hermes_attachments_message_id", "message_id"),
    ):
        op.create_index(idx, "hermes_attachments", [col], unique=False)

    # 2. 快捷提示词
    if not _has_table("hermes_quick_prompts"):
        op.create_table(
            "hermes_quick_prompts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("title", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("icon", sa.String(length=50), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=True),
            sa.Column("is_builtin", sa.Boolean(), nullable=True),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index(
        "ix_hermes_quick_prompts_owner_id",
        "hermes_quick_prompts",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hermes_quick_prompts_owner_id", table_name="hermes_quick_prompts")
    op.drop_table("hermes_quick_prompts")

    for idx in (
        "ix_hermes_attachments_message_id",
        "ix_hermes_attachments_session_id",
        "ix_hermes_attachments_user_id",
    ):
        op.drop_index(idx, table_name="hermes_attachments")
    op.drop_table("hermes_attachments")
