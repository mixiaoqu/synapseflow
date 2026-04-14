"""add_document_size_version

Revision ID: 960187b5411e
Revises:
Create Date: 2026-03-13 11:35:19.949647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '960187b5411e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _documents_has_column(conn, col_name: str) -> bool:
    """检查 documents 表是否有指定列"""
    inspector = inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('documents')]
    return col_name in cols


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    conn = op.get_bind()
    inspector = inspect(conn)

    if 'documents' not in inspector.get_table_names():
        op.create_table(
            'documents',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('document_type', sa.String(50), nullable=True),
            sa.Column('size', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_documents_user_id', 'documents', ['user_id'])
    else:
        if not _documents_has_column(conn, 'size'):
            op.add_column('documents', sa.Column('size', sa.Integer(), nullable=False, server_default='0'))
        if not _documents_has_column(conn, 'version'):
            op.add_column('documents', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    conn = op.get_bind()
    try:
        if _documents_has_column(conn, 'size'):
            op.drop_column('documents', 'size')
        if _documents_has_column(conn, 'version'):
            op.drop_column('documents', 'version')
    except Exception:
        pass  # 表可能不存在
