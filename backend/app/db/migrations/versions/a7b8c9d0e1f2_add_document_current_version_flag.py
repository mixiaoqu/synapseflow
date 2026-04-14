"""add_document_current_version_flag

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _documents_has_column(conn, column_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'documents' AND column_name = :column_name
            """
        ),
        {"column_name": column_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()

    if not _documents_has_column(conn, "is_current"):
        op.add_column(
            "documents",
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        )

    conn.execute(sa.text("UPDATE documents SET is_current = true WHERE is_current IS NULL"))
    op.create_index("idx_documents_is_current", "documents", ["is_current"])


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_index("idx_documents_is_current", table_name="documents")
    if _documents_has_column(conn, "is_current"):
        op.drop_column("documents", "is_current")
