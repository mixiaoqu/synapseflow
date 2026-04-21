"""add assistant llm model key

Revision ID: fb2c3d4e5f6
Revises: fa1b2c3d4e5f
Create Date: 2026-04-21 11:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "fb2c3d4e5f6"
down_revision: Union[str, None] = "fa1b2c3d4e5f"
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

    if _table_exists(conn, "assistant_profiles") and not _has_column(
        conn,
        "assistant_profiles",
        "llm_model_key",
    ):
        op.add_column(
            "assistant_profiles",
            sa.Column("llm_model_key", sa.String(length=80), nullable=True),
        )

    if _table_exists(conn, "assistant_profiles") and not _has_index(
        conn,
        "assistant_profiles",
        "ix_assistant_profiles_llm_model_key",
    ):
        op.create_index(
            "ix_assistant_profiles_llm_model_key",
            "assistant_profiles",
            ["llm_model_key"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "assistant_profiles"):
        if _has_index(conn, "assistant_profiles", "ix_assistant_profiles_llm_model_key"):
            op.drop_index("ix_assistant_profiles_llm_model_key", table_name="assistant_profiles")
        if _has_column(conn, "assistant_profiles", "llm_model_key"):
            op.drop_column("assistant_profiles", "llm_model_key")
