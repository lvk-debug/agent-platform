"""
客服评测接入 DeepEval：SupportEvaluation 新增结果列

Revision ID: support_deepeval_cols_001
Revises: scheduled_tasks_001
Create Date: 2026-09-19 00:00:00.000000

内容：
1. support_evaluations.deepeval_scores      各指标分（JSON）
2. support_evaluations.deepeval_overall     综合分（Float）
3. support_evaluations.deepeval_reasoning   综合理由（Text）

说明：自研四维度 LLM 裁判已移除，自动分改由 DeepEval 产出；原 auto_* 列保留不再写入。
注意：本项目开发期靠 Base.metadata.create_all() 自动建表，故本迁移对"列已存在"做幂等处理。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "support_deepeval_cols_001"
down_revision: str | None = "scheduled_tasks_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "support_evaluations"
_COLUMNS = {
    "deepeval_scores": sa.JSON(),
    "deepeval_overall": sa.Float(),
    "deepeval_reasoning": sa.Text(),
}


def _existing_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    existing = _existing_columns()
    if not existing:
        # 表尚未建立（全新库由 create_all 负责），无需处理
        return
    for name, col_type in _COLUMNS.items():
        if name not in existing:
            op.add_column(_TABLE, sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    existing = _existing_columns()
    for name in _COLUMNS:
        if name in existing:
            op.drop_column(_TABLE, name)
