"""add pg_trgm indexes for embedding search_text lexical retrieval

Revision ID: a9b8c7d6e5f4
Revises: f2b3c4d5e6f7
Create Date: 2026-04-06

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "f2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_search_text_trgm
        ON embeddings
        USING GIN ((lower(search_text)) gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_search_text_compact_trgm
        ON embeddings
        USING GIN ((regexp_replace(lower(search_text), '[[:space:]]+', '', 'g')) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_search_text_compact_trgm")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_search_text_trgm")
