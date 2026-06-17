"""add document parse state fields

Revision ID: 4e6f8a0b2c3d
Revises: 3e5f7a9b1c2d
Create Date: 2026-06-17 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "4e6f8a0b2c3d"
down_revision: Union[str, None] = "3e5f7a9b1c2d"
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


def _drop_column_if_exists(conn, table_name: str, column_name: str) -> None:
    if _has_column(conn, table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "documents"):
        return

    _add_column_if_missing(
        conn,
        "documents",
        sa.Column("parse_status", sa.String(length=20), nullable=True, server_default="parsed"),
    )
    _add_column_if_missing(conn, "documents", sa.Column("parse_error", sa.Text(), nullable=True))
    _add_column_if_missing(
        conn,
        "documents",
        sa.Column("parse_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        conn,
        "documents",
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        conn,
        "documents",
        sa.Column("staged_file_path", sa.String(length=1024), nullable=True),
    )
    _add_column_if_missing(
        conn,
        "documents",
        sa.Column("staged_file_name", sa.String(length=255), nullable=True),
    )
    _add_column_if_missing(
        conn,
        "documents",
        sa.Column("staged_file_size", sa.Integer(), nullable=True),
    )
    _add_column_if_missing(
        conn,
        "documents",
        sa.Column("staged_file_hash", sa.String(length=64), nullable=True),
    )

    op.execute(
        """
        UPDATE documents
        SET parse_status = 'parsed'
        WHERE parse_status IS NULL OR parse_status = '';
        """
    )
    op.alter_column("documents", "parse_status", nullable=False, server_default=None)
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_parse_status ON documents (parse_status)")


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "documents"):
        return

    op.execute("DROP INDEX IF EXISTS ix_documents_parse_status")
    for column_name in (
        "staged_file_hash",
        "staged_file_size",
        "staged_file_name",
        "staged_file_path",
        "parsed_at",
        "parse_started_at",
        "parse_error",
        "parse_status",
    ):
        _drop_column_if_exists(conn, "documents", column_name)
