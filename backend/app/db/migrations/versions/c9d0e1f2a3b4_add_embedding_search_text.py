"""add embedding search_text and retarget chunk_tsv

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-04-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE embeddings
        ADD COLUMN IF NOT EXISTS search_text TEXT;
        """
    )
    op.execute(
        """
        UPDATE embeddings
        SET search_text = coalesce(search_text, chunk_text, '')
        WHERE search_text IS NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE embeddings
        ALTER COLUMN search_text SET NOT NULL;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION embeddings_set_chunk_tsv()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.chunk_tsv := to_tsvector('simple', coalesce(NEW.search_text, ''));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS embeddings_chunk_tsv_bi ON embeddings")
    op.execute(
        """
        CREATE TRIGGER embeddings_chunk_tsv_bi
        BEFORE INSERT OR UPDATE OF chunk_text, search_text ON embeddings
        FOR EACH ROW
        EXECUTE FUNCTION embeddings_set_chunk_tsv()
        """
    )
    op.execute(
        """
        UPDATE embeddings
        SET chunk_tsv = to_tsvector('simple', coalesce(search_text, ''));
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS embeddings_chunk_tsv_bi ON embeddings")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION embeddings_set_chunk_tsv()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.chunk_tsv := to_tsvector('simple', coalesce(NEW.chunk_text, ''));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER embeddings_chunk_tsv_bi
        BEFORE INSERT OR UPDATE OF chunk_text ON embeddings
        FOR EACH ROW
        EXECUTE FUNCTION embeddings_set_chunk_tsv()
        """
    )
    op.execute("ALTER TABLE embeddings DROP COLUMN IF EXISTS search_text")
