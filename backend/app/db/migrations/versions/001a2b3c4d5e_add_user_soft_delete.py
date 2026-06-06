"""add user soft delete

Revision ID: 001a2b3c4d5e
Revises: ff7a8b9c0d1e, 6a7b8c9d0e1f
Create Date: 2026-06-05 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "001a2b3c4d5e"
down_revision: Union[str, tuple[str, ...], None] = ("ff7a8b9c0d1e", "6a7b8c9d0e1f")
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
    if _table_exists(conn, "users") and not _has_column(conn, "users", "deleted_at"):
        op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    if _table_exists(conn, "users") and not _has_index(conn, "users", "ix_users_deleted_at"):
        op.create_index("ix_users_deleted_at", "users", ["deleted_at"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "users"):
        if _has_index(conn, "users", "ix_users_deleted_at"):
            op.drop_index("ix_users_deleted_at", table_name="users")
        if _has_column(conn, "users", "deleted_at"):
            op.drop_column("users", "deleted_at")
