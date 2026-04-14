"""add document index state fields

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-04-03 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS index_status VARCHAR(20);
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS index_error TEXT;
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS content_hash VARCHAR(32);
        """
    )
    op.execute(
        """
        UPDATE documents
        SET content_hash = md5(coalesce(content, ''))
        WHERE content_hash IS NULL OR content_hash = '';
        """
    )
    op.execute(
        """
        UPDATE documents
        SET index_status = CASE
            WHEN indexed_at IS NOT NULL THEN 'indexed'
            ELSE 'queued'
        END
        WHERE index_status IS NULL OR index_status = '';
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        ALTER COLUMN content_hash SET NOT NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        ALTER COLUMN index_status SET NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_index_status
        ON documents (index_status);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_index_status")
    op.execute(
        """
        ALTER TABLE documents
        DROP COLUMN IF EXISTS content_hash;
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        DROP COLUMN IF EXISTS index_error;
        """
    )
    op.execute(
        """
        ALTER TABLE documents
        DROP COLUMN IF EXISTS index_status;
        """
    )
