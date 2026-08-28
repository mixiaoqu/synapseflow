"""Repair business tool tables.

Revision ID: 2f3a4b5c6d7e
Revises: 2e3f4a5b6c7d
Create Date: 2026-07-02 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "2f3a4b5c6d7e"
down_revision: Union[str, None] = "2e3f4a5b6c7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return index_name in {item["name"] for item in inspect(conn).get_indexes(table_name)}


def _create_index_if_missing(
    conn,
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if _table_exists(conn, table_name) and not _index_exists(conn, table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "business_tools"):
        op.create_table(
            "business_tools",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("tool_key", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("method", sa.String(length=10), nullable=False),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("auth_config", sa.JSON(), nullable=False),
            sa.Column("params_schema", sa.JSON(), nullable=False),
            sa.Column("context_mapping", sa.JSON(), nullable=False),
            sa.Column("request_mapping", sa.JSON(), nullable=False),
            sa.Column("response_mapping", sa.JSON(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("team_id", "tool_key", name="uq_business_tools_team_key"),
        )

    _create_index_if_missing(conn, "ix_business_tools_enabled", "business_tools", ["enabled"])
    _create_index_if_missing(conn, "ix_business_tools_id", "business_tools", ["id"])
    _create_index_if_missing(conn, "ix_business_tools_team_id", "business_tools", ["team_id"])
    _create_index_if_missing(conn, "ix_business_tools_tool_key", "business_tools", ["tool_key"])

    if not _table_exists(conn, "project_app_business_tool_bindings"):
        op.create_table(
            "project_app_business_tool_bindings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_app_id", sa.Integer(), nullable=False),
            sa.Column("business_tool_id", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["business_tool_id"], ["business_tools.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_app_id",
                "business_tool_id",
                name="uq_project_app_business_tool_bindings_app_tool",
            ),
        )

    _create_index_if_missing(
        conn,
        "ix_project_app_business_tool_bindings_business_tool_id",
        "project_app_business_tool_bindings",
        ["business_tool_id"],
    )
    _create_index_if_missing(
        conn,
        "ix_project_app_business_tool_bindings_enabled",
        "project_app_business_tool_bindings",
        ["enabled"],
    )
    _create_index_if_missing(
        conn,
        "ix_project_app_business_tool_bindings_id",
        "project_app_business_tool_bindings",
        ["id"],
    )
    _create_index_if_missing(
        conn,
        "ix_project_app_business_tool_bindings_project_app_id",
        "project_app_business_tool_bindings",
        ["project_app_id"],
    )


def downgrade() -> None:
    # This repair migration may be a no-op on databases where the previous
    # revision already created the tables, so downgrade must not drop them.
    return
