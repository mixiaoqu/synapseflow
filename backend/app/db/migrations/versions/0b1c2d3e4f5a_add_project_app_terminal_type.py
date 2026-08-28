"""add project app terminal type

Revision ID: 0b1c2d3e4f5a
Revises: 8c9d0e1f2a3b
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0b1c2d3e4f5a"
down_revision: Union[str, None] = "8c9d0e1f2a3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "project_apps") and not _has_column(conn, "project_apps", "terminal_type"):
        op.add_column(
            "project_apps",
            sa.Column("terminal_type", sa.String(length=40), nullable=False, server_default="web"),
        )
        op.alter_column("project_apps", "terminal_type", server_default=None)


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "project_apps") and _has_column(conn, "project_apps", "terminal_type"):
        op.drop_column("project_apps", "terminal_type")
