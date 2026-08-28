"""Repair business tool platform schema after revision drift.

Revision ID: 406b4d2e7f8a
Revises: 304b6c8d0e2f
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "406b4d2e7f8a"
down_revision: Union[str, None] = "304b6c8d0e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BUSINESS_TOOL_PLATFORM_TABLES = (
    "business_tool_call_logs",
    "project_app_business_tool_bindings",
    "business_tool_implementations",
    "business_apis",
    "business_tools",
    "business_connections",
)

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "business_connections": {
        "id",
        "team_id",
        "name",
        "description",
        "environment",
        "base_url",
        "auth_type",
        "auth_secret_ref",
        "auth_header_name",
        "enabled",
        "status",
        "last_tested_at",
        "last_test_error",
        "created_at",
        "updated_at",
    },
    "business_apis": {
        "id",
        "team_id",
        "connection_id",
        "api_key",
        "name",
        "description",
        "method",
        "path",
        "request_schema",
        "response_schema",
        "source_type",
        "source_version",
        "enabled",
        "created_at",
        "updated_at",
    },
    "business_tools": {
        "id",
        "team_id",
        "tool_key",
        "name",
        "description",
        "typical_queries",
        "params_schema",
        "risk_level",
        "requires_confirmation",
        "status",
        "last_tested_at",
        "last_test_error",
        "enabled",
        "created_at",
        "updated_at",
    },
    "business_tool_implementations": {
        "id",
        "business_tool_id",
        "business_api_id",
        "implementation_type",
        "context_binding",
        "request_mapping",
        "response_mapping",
        "status",
        "last_tested_at",
        "last_test_error",
        "priority",
        "enabled",
        "created_at",
        "updated_at",
    },
    "project_app_business_tool_bindings": {
        "id",
        "project_app_id",
        "business_tool_id",
        "enabled",
        "created_at",
        "updated_at",
    },
    "business_tool_call_logs": {
        "id",
        "team_id",
        "project_app_id",
        "business_api_id",
        "business_tool_id",
        "business_tool_implementation_id",
        "tool_key",
        "tool_name",
        "api_key",
        "api_name",
        "session_id",
        "actor_user_id",
        "external_user_id",
        "status",
        "http_status",
        "duration_ms",
        "request_payload",
        "response_payload",
        "error_message",
        "created_at",
    },
}


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    return table_name in inspect(conn).get_table_names()


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    conn = op.get_bind()
    return {column["name"] for column in inspect(conn).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    conn = op.get_bind()
    return {item["name"] for item in inspect(conn).get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if _table_exists(table_name) and index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns, unique=False)


def _drop_table_if_exists(table_name: str) -> None:
    if _table_exists(table_name):
        op.drop_table(table_name)


def _schema_requires_rebuild() -> bool:
    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        if not expected_columns.issubset(_column_names(table_name)):
            return True
    return False


def _create_business_connections_table() -> None:
    if not _table_exists("business_connections"):
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
    for name, columns in (
        ("ix_business_connections_id", ["id"]),
        ("ix_business_connections_team_id", ["team_id"]),
        ("ix_business_connections_environment", ["environment"]),
        ("ix_business_connections_enabled", ["enabled"]),
        ("ix_business_connections_status", ["status"]),
    ):
        _create_index_if_missing(name, "business_connections", columns)


def _create_business_apis_table() -> None:
    if not _table_exists("business_apis"):
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
        _create_index_if_missing(name, "business_apis", columns)


def _create_business_tools_table() -> None:
    if not _table_exists("business_tools"):
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
        _create_index_if_missing(name, "business_tools", columns)


def _create_business_tool_implementations_table() -> None:
    if not _table_exists("business_tool_implementations"):
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
        _create_index_if_missing(name, "business_tool_implementations", columns)


def _create_project_app_business_tool_bindings_table() -> None:
    if not _table_exists("project_app_business_tool_bindings"):
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
        _create_index_if_missing(name, "project_app_business_tool_bindings", columns)


def _create_business_tool_call_logs_table() -> None:
    if not _table_exists("business_tool_call_logs"):
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
        _create_index_if_missing(name, "business_tool_call_logs", columns)


def _rebuild_business_tool_platform_tables() -> None:
    for table_name in BUSINESS_TOOL_PLATFORM_TABLES:
        _drop_table_if_exists(table_name)

    _create_business_connections_table()
    _create_business_apis_table()
    _create_business_tools_table()
    _create_business_tool_implementations_table()
    _create_project_app_business_tool_bindings_table()
    _create_business_tool_call_logs_table()


def _ensure_business_tool_platform_tables() -> None:
    _create_business_connections_table()
    _create_business_apis_table()
    _create_business_tools_table()
    _create_business_tool_implementations_table()
    _create_project_app_business_tool_bindings_table()
    _create_business_tool_call_logs_table()


def upgrade() -> None:
    # 某些数据库已被标记到 304b6c8d0e2f，但实际结构仍停留在旧版工具表。
    if _schema_requires_rebuild():
        _rebuild_business_tool_platform_tables()
        return

    _ensure_business_tool_platform_tables()


def downgrade() -> None:
    # 修复型迁移不尝试反向恢复未知的异常数据库状态。
    return
