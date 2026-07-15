"""add agent integrations

Revision ID: fg8b9c0d1e2f
Revises: 406b4d2e7f8a
Create Date: 2026-07-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "fg8b9c0d1e2f"
down_revision: Union[str, None] = "406b4d2e7f8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=30), nullable=False),
        sa.Column("endpoint_url", sa.Text(), nullable=False),
        sa.Column("transport_type", sa.String(length=30), nullable=False),
        sa.Column("auth_type", sa.String(length=20), nullable=False),
        sa.Column("auth_secret_ref", sa.String(length=255), nullable=True),
        sa.Column("auth_header_name", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "name", name="uq_mcp_servers_team_name"),
    )
    op.create_index(op.f("ix_mcp_servers_id"), "mcp_servers", ["id"], unique=False)
    op.create_index(op.f("ix_mcp_servers_team_id"), "mcp_servers", ["team_id"], unique=False)
    op.create_index(op.f("ix_mcp_servers_environment"), "mcp_servers", ["environment"], unique=False)
    op.create_index(op.f("ix_mcp_servers_transport_type"), "mcp_servers", ["transport_type"], unique=False)
    op.create_index(op.f("ix_mcp_servers_enabled"), "mcp_servers", ["enabled"], unique=False)
    op.create_index(op.f("ix_mcp_servers_status"), "mcp_servers", ["status"], unique=False)

    op.create_table(
        "mcp_tools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mcp_server_id", sa.Integer(), nullable=False),
        sa.Column("raw_name", sa.String(length=180), nullable=False),
        sa.Column("raw_description", sa.Text(), nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("schema_hash", sa.String(length=64), nullable=False),
        sa.Column("sync_status", sa.String(length=20), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["mcp_server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mcp_server_id", "raw_name", name="uq_mcp_tools_server_raw_name"),
    )
    op.create_index(op.f("ix_mcp_tools_id"), "mcp_tools", ["id"], unique=False)
    op.create_index(op.f("ix_mcp_tools_mcp_server_id"), "mcp_tools", ["mcp_server_id"], unique=False)
    op.create_index(op.f("ix_mcp_tools_raw_name"), "mcp_tools", ["raw_name"], unique=False)
    op.create_index(op.f("ix_mcp_tools_schema_hash"), "mcp_tools", ["schema_hash"], unique=False)
    op.create_index(op.f("ix_mcp_tools_sync_status"), "mcp_tools", ["sync_status"], unique=False)

    op.create_table(
        "agent_tools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("mcp_tool_id", sa.Integer(), nullable=False),
        sa.Column("tool_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("agent_description", sa.Text(), nullable=True),
        sa.Column("params_schema", sa.JSON(), nullable=False),
        sa.Column("response_schema", sa.JSON(), nullable=False),
        sa.Column("tool_type", sa.String(length=30), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["mcp_tool_id"], ["mcp_tools.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mcp_tool_id", name="uq_agent_tools_mcp_tool"),
        sa.UniqueConstraint("team_id", "tool_key", name="uq_agent_tools_team_key"),
    )
    op.create_index(op.f("ix_agent_tools_id"), "agent_tools", ["id"], unique=False)
    op.create_index(op.f("ix_agent_tools_team_id"), "agent_tools", ["team_id"], unique=False)
    op.create_index(op.f("ix_agent_tools_mcp_tool_id"), "agent_tools", ["mcp_tool_id"], unique=False)
    op.create_index(op.f("ix_agent_tools_tool_key"), "agent_tools", ["tool_key"], unique=False)
    op.create_index(op.f("ix_agent_tools_tool_type"), "agent_tools", ["tool_type"], unique=False)
    op.create_index(op.f("ix_agent_tools_risk_level"), "agent_tools", ["risk_level"], unique=False)
    op.create_index(op.f("ix_agent_tools_enabled"), "agent_tools", ["enabled"], unique=False)
    op.create_index(op.f("ix_agent_tools_status"), "agent_tools", ["status"], unique=False)

    op.create_table(
        "agent_app_tool_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_app_id", sa.Integer(), nullable=False),
        sa.Column("agent_tool_id", sa.Integer(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
        sa.Column("requires_confirmation_override", sa.Boolean(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_tool_id"], ["agent_tools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_app_id", "agent_tool_id", name="uq_agent_app_tool_bindings_app_tool"),
    )
    op.create_index(op.f("ix_agent_app_tool_bindings_id"), "agent_app_tool_bindings", ["id"], unique=False)
    op.create_index(op.f("ix_agent_app_tool_bindings_project_app_id"), "agent_app_tool_bindings", ["project_app_id"], unique=False)
    op.create_index(op.f("ix_agent_app_tool_bindings_agent_tool_id"), "agent_app_tool_bindings", ["agent_tool_id"], unique=False)
    op.create_index(op.f("ix_agent_app_tool_bindings_enabled"), "agent_app_tool_bindings", ["enabled"], unique=False)

    op.create_table(
        "agent_tool_call_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("project_app_id", sa.Integer(), nullable=True),
        sa.Column("agent_tool_id", sa.Integer(), nullable=True),
        sa.Column("mcp_server_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=100), nullable=True),
        sa.Column("trace_id", sa.String(length=100), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("external_user_id", sa.String(length=255), nullable=True),
        sa.Column("tool_key", sa.String(length=120), nullable=False),
        sa.Column("mcp_tool_name", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_tool_id"], ["agent_tools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mcp_server_id"], ["mcp_servers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_tool_call_logs_id"), "agent_tool_call_logs", ["id"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_team_id"), "agent_tool_call_logs", ["team_id"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_project_app_id"), "agent_tool_call_logs", ["project_app_id"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_agent_tool_id"), "agent_tool_call_logs", ["agent_tool_id"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_mcp_server_id"), "agent_tool_call_logs", ["mcp_server_id"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_session_id"), "agent_tool_call_logs", ["session_id"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_trace_id"), "agent_tool_call_logs", ["trace_id"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_tool_key"), "agent_tool_call_logs", ["tool_key"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_mcp_tool_name"), "agent_tool_call_logs", ["mcp_tool_name"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_status"), "agent_tool_call_logs", ["status"], unique=False)
    op.create_index(op.f("ix_agent_tool_call_logs_created_at"), "agent_tool_call_logs", ["created_at"], unique=False)

    op.drop_table("business_tool_call_logs")
    op.drop_table("project_app_business_tool_bindings")
    op.drop_table("business_tool_implementations")
    op.drop_table("business_tools")
    op.drop_table("business_apis")
    op.drop_table("business_connections")


def downgrade() -> None:
    op.create_table(
        "business_connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=30), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("auth_type", sa.String(length=20), nullable=False),
        sa.Column("auth_secret_ref", sa.String(length=255), nullable=True),
        sa.Column("auth_header_name", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "name", name="uq_business_connections_team_name"),
    )
    op.drop_table("agent_tool_call_logs")
    op.drop_table("agent_app_tool_bindings")
    op.drop_table("agent_tools")
    op.drop_table("mcp_tools")
    op.drop_table("mcp_servers")
