"""add document live version flag

Revision ID: fa1b2c3d4e5f
Revises: f9a0b1c2d3e4
Create Date: 2026-04-20 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "fa1b2c3d4e5f"
down_revision: Union[str, None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def _has_index(conn, table_name: str, index_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return index_name in {item["name"] for item in inspect(conn).get_indexes(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "documents"):
        return

    if not _has_column(conn, "documents", "is_live"):
        op.add_column(
            "documents",
            sa.Column("is_live", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not _has_index(conn, "documents", "ix_documents_is_live"):
        op.create_index("ix_documents_is_live", "documents", ["is_live"], unique=False)

    op.execute("UPDATE documents SET root_id = id WHERE root_id IS NULL")
    op.execute("UPDATE documents SET status = 'draft' WHERE status = 'indexed'")
    op.execute(
        """
        UPDATE documents
        SET is_live = true
        WHERE status = 'published' AND is_current IS TRUE
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_current_per_root
        ON documents ((COALESCE(root_id, id)))
        WHERE is_current IS TRUE
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_live_per_root
        ON documents ((COALESCE(root_id, id)))
        WHERE is_live IS TRUE
        """
    )

    if _table_exists(conn, "embeddings"):
        op.execute(
            """
            DELETE FROM embeddings
            WHERE document_id IN (
                SELECT id
                FROM documents
                WHERE is_current IS NOT TRUE AND is_live IS NOT TRUE
            )
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "documents"):
        return

    op.execute("DROP INDEX IF EXISTS uq_documents_live_per_root")
    op.execute("DROP INDEX IF EXISTS uq_documents_current_per_root")
    if _has_index(conn, "documents", "ix_documents_is_live"):
        op.drop_index("ix_documents_is_live", table_name="documents")
    if _has_column(conn, "documents", "is_live"):
        op.drop_column("documents", "is_live")
