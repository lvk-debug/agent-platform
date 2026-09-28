"""Hermes 能力扩展 - 技能表与会话/运行扩展列

Revision ID: hermes_capability_001
Revises: hermes_001
Create Date: 2026-09-07 00:00:00.000000

内容：
1. 新建 hermes_skills 表（平台自建技能，可 CRUD）
2. hermes_sessions 增加 skills / tools (JSON)
3. hermes_runs 增加 external_run_id（Hermes 上游 run_id，用于 /v1/runs/{id}/stop）
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "hermes_capability_001"
down_revision: Union[str, None] = "hermes_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 会话：技能与工具偏好
    with op.batch_alter_table("hermes_sessions") as batch_op:
        batch_op.add_column(
            sa.Column("skills", sa.JSON(), nullable=True, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("tools", sa.JSON(), nullable=True, server_default="[]")
        )

    # 2. 运行：上游 run_id，用于真正停止生成
    with op.batch_alter_table("hermes_runs") as batch_op:
        batch_op.add_column(
            sa.Column("external_run_id", sa.String(length=100), nullable=True, server_default="")
        )

    # 3. 技能表
    op.create_table(
        "hermes_skills",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("instruction", sa.Text(), server_default=""),
        sa.Column("icon", sa.String(length=20), server_default=""),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_hermes_skills_slug", "hermes_skills", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_hermes_skills_slug", table_name="hermes_skills")
    op.drop_table("hermes_skills")

    with op.batch_alter_table("hermes_runs") as batch_op:
        batch_op.drop_column("external_run_id")

    with op.batch_alter_table("hermes_sessions") as batch_op:
        batch_op.drop_column("tools")
        batch_op.drop_column("skills")
