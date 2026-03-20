"""embedding vector 512 -> 1024 (bge-m3)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 必须先删除向量索引，否则 ALTER COLUMN 会失败
    op.execute("DROP INDEX IF EXISTS embeddings_vector_idx")
    op.execute("TRUNCATE embeddings")
    op.execute("ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(1024)")
    op.execute(
        "CREATE INDEX embeddings_vector_idx ON embeddings "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS embeddings_vector_idx")
    op.execute("TRUNCATE embeddings")
    op.execute("ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(512)")
    op.execute(
        "CREATE INDEX embeddings_vector_idx ON embeddings "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
