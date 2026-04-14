"""add_document_version_fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _documents_has_column(conn, col_name: str) -> bool:
    inspector = inspect(conn)
    if 'documents' not in inspector.get_table_names():
        return False
    cols = [c['name'] for c in inspector.get_columns('documents')]
    return col_name in cols


def upgrade() -> None:
    conn = op.get_bind()
    if not _documents_has_column(conn, 'parent_id'):
        op.add_column('documents', sa.Column('parent_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_documents_parent_id', 'documents', 'documents', ['parent_id'], ['id'], ondelete='SET NULL')
    if not _documents_has_column(conn, 'root_id'):
        op.add_column('documents', sa.Column('root_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_documents_root_id', 'documents', 'documents', ['root_id'], ['id'], ondelete='SET NULL')
    if not _documents_has_column(conn, 'is_latest'):
        op.add_column('documents', sa.Column('is_latest', sa.Boolean(), nullable=False, server_default='true'))

    # 存量数据：parent_id=null, root_id=id, is_latest=True
    conn.execute(sa.text("UPDATE documents SET root_id = id WHERE root_id IS NULL"))
    op.create_index('idx_documents_root_id', 'documents', ['root_id'])
    op.create_index('idx_documents_is_latest', 'documents', ['is_latest'])


def downgrade() -> None:
    conn = op.get_bind()
    op.drop_index('idx_documents_is_latest', table_name='documents')
    op.drop_index('idx_documents_root_id', table_name='documents')
    if _documents_has_column(conn, 'is_latest'):
        op.drop_column('documents', 'is_latest')
    if _documents_has_column(conn, 'root_id'):
        op.drop_constraint('fk_documents_root_id', 'documents', type_='foreignkey')
        op.drop_column('documents', 'root_id')
    if _documents_has_column(conn, 'parent_id'):
        op.drop_constraint('fk_documents_parent_id', 'documents', type_='foreignkey')
        op.drop_column('documents', 'parent_id')
