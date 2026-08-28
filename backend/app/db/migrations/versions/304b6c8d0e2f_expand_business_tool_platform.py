"""Rebuild business tool platform around connection/api/tool separation.

Revision ID: 304b6c8d0e2f
Revises: 2f3a4b5c6d7e
Create Date: 2026-07-04 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "304b6c8d0e2f"
down_revision: Union[str, None] = "2f3a4b5c6d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    return table_name in inspect(conn).get_table_names()


def _drop_table_if_exists(table_name: str) -> None:
    if _table_exists(table_name):
        op.drop_table(table_name)


def upgrade() -> None:
    # 当前版本直接采用最终结构，不保留旧版工具表字段和数据迁移逻辑。
    for table_name in (
        "business_tool_call_logs",
        "project_app_business_tool_bindings",
        "business_tool_implementations",
        "business_apis",
        "business_tools",
        "business_connections",
    ):
        _drop_table_if_exists(table_name)

    op.create_table(
        "business_connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=30), nullable=False, server_default="production"),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("auth_type", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("auth_secret_ref", sa.String(length=255), nullable=True),
        sa.Column("auth_header_name", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="untested"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "name", name="uq_business_connections_team_name"),
    )
    op.create_index("ix_business_connections_id", "business_connections", ["id"], unique=False)
    op.create_index("ix_business_connections_team_id", "business_connections", ["team_id"], unique=False)
    op.create_index("ix_business_connections_environment", "business_connections", ["environment"], unique=False)
    op.create_index("ix_business_connections_enabled", "business_connections", ["enabled"], unique=False)
    op.create_index("ix_business_connections_status", "business_connections", ["status"], unique=False)

    op.create_table(
        "business_apis",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("api_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=False, server_default="GET"),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("request_schema", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("response_schema", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("source_version", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["business_connections.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "api_key", name="uq_business_apis_team_key"),
    )
    for name, columns in (
        ("ix_business_apis_id", ["id"]),
        ("ix_business_apis_team_id", ["team_id"]),
        ("ix_business_apis_connection_id", ["connection_id"]),
        ("ix_business_apis_api_key", ["api_key"]),
        ("ix_business_apis_source_type", ["source_type"]),
        ("ix_business_apis_enabled", ["enabled"]),
    ):
        op.create_index(name, "business_apis", columns, unique=False)

    op.create_table(
        "business_tools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("tool_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("typical_queries", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("params_schema", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("risk_level", sa.String(length=20), nullable=False, server_default="low"),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "tool_key", name="uq_business_tools_team_key"),
    )
    for name, columns in (
        ("ix_business_tools_id", ["id"]),
        ("ix_business_tools_team_id", ["team_id"]),
        ("ix_business_tools_tool_key", ["tool_key"]),
        ("ix_business_tools_risk_level", ["risk_level"]),
        ("ix_business_tools_status", ["status"]),
        ("ix_business_tools_enabled", ["enabled"]),
    ):
        op.create_index(name, "business_tools", columns, unique=False)

    op.create_table(
        "business_tool_implementations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_tool_id", sa.Integer(), nullable=False),
        sa.Column("business_api_id", sa.Integer(), nullable=False),
        sa.Column("implementation_type", sa.String(length=30), nullable=False, server_default="http"),
        sa.Column("context_binding", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("request_mapping", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("response_mapping", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_tool_id"], ["business_tools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_api_id"], ["business_apis.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_tool_id",
            "business_api_id",
            name="uq_business_tool_implementations_tool_api",
        ),
    )
    for name, columns in (
        ("ix_business_tool_implementations_id", ["id"]),
        ("ix_business_tool_implementations_business_tool_id", ["business_tool_id"]),
        ("ix_business_tool_implementations_business_api_id", ["business_api_id"]),
        ("ix_business_tool_implementations_implementation_type", ["implementation_type"]),
        ("ix_business_tool_implementations_status", ["status"]),
        ("ix_business_tool_implementations_priority", ["priority"]),
        ("ix_business_tool_implementations_enabled", ["enabled"]),
    ):
        op.create_index(name, "business_tool_implementations", columns, unique=False)

    op.create_table(
        "project_app_business_tool_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_app_id", sa.Integer(), nullable=False),
        sa.Column("business_tool_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
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
    for name, columns in (
        ("ix_project_app_business_tool_bindings_id", ["id"]),
        ("ix_project_app_business_tool_bindings_project_app_id", ["project_app_id"]),
        ("ix_project_app_business_tool_bindings_business_tool_id", ["business_tool_id"]),
        ("ix_project_app_business_tool_bindings_enabled", ["enabled"]),
    ):
        op.create_index(name, "project_app_business_tool_bindings", columns, unique=False)

    op.create_table(
        "business_tool_call_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("project_app_id", sa.Integer(), nullable=True),
        sa.Column("business_api_id", sa.Integer(), nullable=True),
        sa.Column("business_tool_id", sa.Integer(), nullable=True),
        sa.Column("business_tool_implementation_id", sa.Integer(), nullable=True),
        sa.Column("tool_key", sa.String(length=120), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("api_key", sa.String(length=120), nullable=True),
        sa.Column("api_name", sa.String(length=100), nullable=True),
        sa.Column("session_id", sa.String(length=100), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("external_user_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("response_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["business_api_id"], ["business_apis.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["business_tool_id"], ["business_tools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["business_tool_implementation_id"],
            ["business_tool_implementations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_business_tool_call_logs_id", ["id"]),
        ("ix_business_tool_call_logs_team_id", ["team_id"]),
        ("ix_business_tool_call_logs_project_app_id", ["project_app_id"]),
        ("ix_business_tool_call_logs_business_api_id", ["business_api_id"]),
        ("ix_business_tool_call_logs_business_tool_id", ["business_tool_id"]),
        (
            "ix_business_tool_call_logs_business_tool_implementation_id",
            ["business_tool_implementation_id"],
        ),
        ("ix_business_tool_call_logs_tool_key", ["tool_key"]),
        ("ix_business_tool_call_logs_api_key", ["api_key"]),
        ("ix_business_tool_call_logs_session_id", ["session_id"]),
        ("ix_business_tool_call_logs_status", ["status"]),
        ("ix_business_tool_call_logs_created_at", ["created_at"]),
    ):
        op.create_index(name, "business_tool_call_logs", columns, unique=False)


def downgrade() -> None:
    for table_name in (
        "business_tool_call_logs",
        "project_app_business_tool_bindings",
        "business_tool_implementations",
        "business_apis",
        "business_tools",
        "business_connections",
    ):
        _drop_table_if_exists(table_name)

    op.create_table(
        "business_tools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("tool_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("auth_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("params_schema", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("context_mapping", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("request_mapping", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("response_mapping", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "tool_key", name="uq_business_tools_team_key"),
    )
    op.create_index("ix_business_tools_enabled", "business_tools", ["enabled"], unique=False)
    op.create_index("ix_business_tools_id", "business_tools", ["id"], unique=False)
    op.create_index("ix_business_tools_team_id", "business_tools", ["team_id"], unique=False)
    op.create_index("ix_business_tools_tool_key", "business_tools", ["tool_key"], unique=False)

    op.create_table(
        "project_app_business_tool_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_app_id", sa.Integer(), nullable=False),
        sa.Column("business_tool_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
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
    op.create_index(
        "ix_project_app_business_tool_bindings_business_tool_id",
        "project_app_business_tool_bindings",
        ["business_tool_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_app_business_tool_bindings_enabled",
        "project_app_business_tool_bindings",
        ["enabled"],
        unique=False,
    )
    op.create_index(
        "ix_project_app_business_tool_bindings_id",
        "project_app_business_tool_bindings",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_project_app_business_tool_bindings_project_app_id",
        "project_app_business_tool_bindings",
        ["project_app_id"],
        unique=False,
    )
