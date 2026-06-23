"""add document source file fields

Revision ID: 1d2e3f4a5b6c
Revises: 0c1d2e3f4a5b
Create Date: 2026-06-22 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "1d2e3f4a5b6c"
down_revision: Union[str, None] = "0c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def _add_column_if_missing(conn, table_name: str, column: sa.Column) -> None:
    if not _has_column(conn, table_name, str(column.name)):
        op.add_column(table_name, column)


def upgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "documents"):
        for column in (
            sa.Column("source_storage_provider", sa.String(length=50), nullable=True),
            sa.Column("source_bucket_name", sa.String(length=255), nullable=True),
            sa.Column("source_object_key", sa.String(length=1024), nullable=True),
            sa.Column("source_file_name", sa.String(length=255), nullable=True),
            sa.Column("source_file_size", sa.Integer(), nullable=True),
            sa.Column("source_content_type", sa.String(length=255), nullable=True),
            sa.Column("source_etag", sa.String(length=255), nullable=True),
        ):
            _add_column_if_missing(conn, "documents", column)

    if _table_exists(conn, "document_upload_sessions"):
        _add_column_if_missing(
            conn,
            "document_upload_sessions",
            sa.Column(
                "document_id",
                sa.Integer(),
                sa.ForeignKey("documents.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_document_upload_sessions_document_id "
            "ON document_upload_sessions (document_id)"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "document_upload_sessions"):
        op.execute("DROP INDEX IF EXISTS ix_document_upload_sessions_document_id")
        if _has_column(conn, "document_upload_sessions", "document_id"):
            op.drop_column("document_upload_sessions", "document_id")

    if _table_exists(conn, "documents"):
        for column_name in (
            "source_etag",
            "source_content_type",
            "source_file_size",
            "source_file_name",
            "source_object_key",
            "source_bucket_name",
            "source_storage_provider",
        ):
            if _has_column(conn, "documents", column_name):
                op.drop_column("documents", column_name)
