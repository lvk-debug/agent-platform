"""add epub, source_type, url

Revision ID: add_epub_source_type_url
Revises:
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa

revision = "add_epub_source_type_url"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 source_type 列
    op.add_column(
        "documents", sa.Column("source_type", sa.String(20), server_default="file")
    )
    # 添加 url 列
    op.add_column("documents", sa.Column("url", sa.String(2000), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "url")
    op.drop_column("documents", "source_type")
