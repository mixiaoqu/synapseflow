"""add assistant created by audit field

Revision ID: f9a0b1c2d3e4
Revises: f8b9c0d1e2f3
Create Date: 2026-04-16 10:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, None] = "f8b9c0d1e2f3"
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


def _has_fk(conn, table_name: str, fk_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return fk_name in {item["name"] for item in inspect(conn).get_foreign_keys(table_name)}


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "assistant_profiles") and not _has_column(
        conn,
        "assistant_profiles",
        "created_by_user_id",
    ):
        op.add_column(
            "assistant_profiles",
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        )

    if _table_exists(conn, "assistant_profiles") and not _has_index(
        conn,
        "assistant_profiles",
        "ix_assistant_profiles_created_by_user_id",
    ):
        op.create_index(
            "ix_assistant_profiles_created_by_user_id",
            "assistant_profiles",
            ["created_by_user_id"],
            unique=False,
        )

    if _table_exists(conn, "assistant_profiles") and not _has_fk(
        conn,
        "assistant_profiles",
        "fk_assistant_profiles_created_by_user_id_users",
    ):
        op.create_foreign_key(
            "fk_assistant_profiles_created_by_user_id_users",
            "assistant_profiles",
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "assistant_profiles"):
        if _has_fk(conn, "assistant_profiles", "fk_assistant_profiles_created_by_user_id_users"):
            op.drop_constraint(
                "fk_assistant_profiles_created_by_user_id_users",
                "assistant_profiles",
                type_="foreignkey",
            )
        if _has_index(conn, "assistant_profiles", "ix_assistant_profiles_created_by_user_id"):
            op.drop_index("ix_assistant_profiles_created_by_user_id", table_name="assistant_profiles")
        if _has_column(conn, "assistant_profiles", "created_by_user_id"):
            op.drop_column("assistant_profiles", "created_by_user_id")
