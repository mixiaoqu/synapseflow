"""embeddings 增加 chunk_tsv（全文检索）及触发器维护

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-26

说明：使用 PostgreSQL tsvector + ts_rank_cd 作词法稀疏通道（非 Elasticsearch 的 Okapi BM25）。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS chunk_tsv tsvector;
        """
    )
    op.execute(
        """
        UPDATE embeddings
        SET chunk_tsv = to_tsvector('simple', coalesce(chunk_text, ''))
        WHERE chunk_tsv IS NULL;
        """
    )
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
    op.execute("DROP TRIGGER IF EXISTS embeddings_chunk_tsv_bi ON embeddings")
    op.execute(
        """
        CREATE TRIGGER embeddings_chunk_tsv_bi
        BEFORE INSERT OR UPDATE OF chunk_text ON embeddings
        FOR EACH ROW
        EXECUTE FUNCTION embeddings_set_chunk_tsv()
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_tsv
        ON embeddings USING GIN (chunk_tsv);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_chunk_tsv")
    op.execute("DROP TRIGGER IF EXISTS embeddings_chunk_tsv_bi ON embeddings")
    op.execute("DROP FUNCTION IF EXISTS embeddings_set_chunk_tsv()")
    op.execute("ALTER TABLE embeddings DROP COLUMN IF EXISTS chunk_tsv")
