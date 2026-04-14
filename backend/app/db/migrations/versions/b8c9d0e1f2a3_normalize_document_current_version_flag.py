"""normalize_document_current_version_flag

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-02 00:00:01.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(conn, index_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = current_schema() AND indexname = :index_name
            """
        ),
        {"index_name": index_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY root_id
                        ORDER BY
                            CASE WHEN is_latest THEN 0 ELSE 1 END,
                            version DESC,
                            updated_at DESC,
                            id DESC
                    ) AS rn
                FROM documents
                WHERE root_id IS NOT NULL
            )
            UPDATE documents AS d
            SET is_current = CASE WHEN ranked.rn = 1 THEN true ELSE false END
            FROM ranked
            WHERE d.id = ranked.id
            """
        )
    )

    if not _index_exists(conn, "uq_documents_root_id_current"):
        conn.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX uq_documents_root_id_current
                ON documents (root_id)
                WHERE is_current IS TRUE
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _index_exists(conn, "uq_documents_root_id_current"):
        conn.execute(sa.text("DROP INDEX uq_documents_root_id_current"))
