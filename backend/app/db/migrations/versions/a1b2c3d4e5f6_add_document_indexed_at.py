"""add_document_indexed_at

Revision ID: a1b2c3d4e5f6
Revises: 960187b5411e
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '960187b5411e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _documents_has_column(conn, col_name: str) -> bool:
    """检查 documents 表是否有指定列"""
    inspector = inspect(conn)
    if 'documents' not in inspector.get_table_names():
        return False
    cols = [c['name'] for c in inspector.get_columns('documents')]
    return col_name in cols


def upgrade() -> None:
    conn = op.get_bind()
    if not _documents_has_column(conn, 'indexed_at'):
        op.add_column('documents', sa.Column('indexed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if _documents_has_column(conn, 'indexed_at'):
        op.drop_column('documents', 'indexed_at')
