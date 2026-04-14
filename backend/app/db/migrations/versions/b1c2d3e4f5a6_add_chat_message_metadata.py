"""add metadata to chat messages for persisted sources

Revision ID: b1c2d3e4f5a6
Revises: aa1b2c3d4e5f
Create Date: 2026-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "aa1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {item["name"] for item in inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "chat_messages") and not _has_column(conn, "chat_messages", "metadata"):
        op.add_column("chat_messages", sa.Column("metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "chat_messages") and _has_column(conn, "chat_messages", "metadata"):
        op.drop_column("chat_messages", "metadata")
