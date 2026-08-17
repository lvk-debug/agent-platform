"""add chunk_strategy to documents

Revision ID: a1b2c3d4e5f6
Revises: 045d563e7600
Create Date: 2026-08-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '045d563e7600'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 chunk_strategy 列
    op.add_column('documents', sa.Column('chunk_strategy', sa.String(20), nullable=True, server_default='sliding_window'))

    # 将 status 列从 Enum 改为 String（SQLite 兼容）
    # 使用 batch_alter_table 来修改列类型
    with op.batch_alter_table('documents') as batch_op:
        batch_op.alter_column('status',
                              type_=sa.String(20),
                              existing_type=sa.Enum('pending', 'processing', 'completed', 'failed', name='doc_status_enum'),
                              nullable=True)


def downgrade() -> None:
    op.drop_column('documents', 'chunk_strategy')

    # 恢复 status 列为 Enum 类型
    with op.batch_alter_table('documents') as batch_op:
        batch_op.alter_column('status',
                              type_=sa.Enum('pending', 'processing', 'completed', 'failed', name='doc_status_enum'),
                              existing_type=sa.String(20),
                              nullable=True)
