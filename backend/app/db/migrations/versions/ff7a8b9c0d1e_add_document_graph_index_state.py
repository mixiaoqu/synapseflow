"""add document graph index state fields

Revision ID: ff7a8b9c0d1e
Revises: fe6a7b8c9d0e
Create Date: 2026-05-12 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "ff7a8b9c0d1e"
down_revision: Union[str, None] = "1b2c3d4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS graph_index_status VARCHAR(20);
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS graph_index_error TEXT;
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS graph_indexed_at TIMESTAMPTZ;
        """
    )
    op.execute(
        """
        UPDATE documents
        SET graph_index_status = 'queued'
        WHERE graph_index_status IS NULL OR graph_index_status = '';
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        ALTER COLUMN graph_index_status SET NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_graph_index_status
        ON documents (graph_index_status);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_graph_index_status")
    op.execute(
        """
        ALTER TABLE documents
        DROP COLUMN IF EXISTS graph_indexed_at;
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        DROP COLUMN IF EXISTS graph_index_error;
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        DROP COLUMN IF EXISTS graph_index_status;
        """
    )
