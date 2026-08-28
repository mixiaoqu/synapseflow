"""Unify MCP integrations as tool providers.

Revision ID: lm4h5c6d7e8f
Revises: kl3g4b5c6d7e
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "lm4h5c6d7e8f"
down_revision: Union[str, Sequence[str], None] = "kl3g4b5c6d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("mcp_servers", "tool_providers")
    op.drop_constraint("uq_mcp_servers_team_name", "tool_providers", type_="unique")
    op.add_column("tool_providers", sa.Column("code", sa.String(length=80), nullable=True))
    op.execute("UPDATE tool_providers SET code = 'provider_' || id::text")
    op.alter_column("tool_providers", "code", nullable=False)
    op.alter_column("tool_providers", "endpoint_url", new_column_name="base_url")
    op.alter_column("tool_providers", "status", new_column_name="health_status")
    op.execute("UPDATE tool_providers SET transport_type = 'mcp_http' WHERE transport_type = 'http'")
    op.alter_column("tool_providers", "transport_type", server_default="business_http")
    op.drop_index("ix_mcp_servers_environment", table_name="tool_providers")
    op.drop_column("tool_providers", "environment")
    for old_name in (
        "ix_mcp_servers_id",
        "ix_mcp_servers_team_id",
        "ix_mcp_servers_transport_type",
        "ix_mcp_servers_enabled",
        "ix_mcp_servers_status",
    ):
        op.drop_index(old_name, table_name="tool_providers")
    for column in ("id", "team_id", "transport_type", "enabled", "health_status"):
        op.create_index(f"ix_tool_providers_{column}", "tool_providers", [column])
    op.create_unique_constraint(
        "uq_tool_providers_team_code",
        "tool_providers",
        ["team_id", "code"],
    )

    op.add_column("agent_tools", sa.Column("provider_id", sa.Integer(), nullable=True))
    op.add_column("agent_tools", sa.Column("external_name", sa.String(length=180), nullable=True))
    op.add_column("agent_tools", sa.Column("external_description", sa.Text(), nullable=True))
    op.add_column("agent_tools", sa.Column("input_schema", sa.JSON(), nullable=True))
    op.add_column("agent_tools", sa.Column("output_schema", sa.JSON(), nullable=True))
    op.add_column("agent_tools", sa.Column("required_context", sa.JSON(), nullable=True))
    op.add_column("agent_tools", sa.Column("raw_manifest", sa.JSON(), nullable=True))
    op.add_column("agent_tools", sa.Column("schema_hash", sa.String(length=64), nullable=True))
    op.add_column("agent_tools", sa.Column("sync_status", sa.String(length=20), nullable=True))
    op.add_column("agent_tools", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_tools", sa.Column("publish_status", sa.String(length=20), nullable=True))
    op.add_column("agent_tools", sa.Column("approved_schema_hash", sa.String(length=64), nullable=True))
    op.execute(
        """
        UPDATE agent_tools AS agent
        SET provider_id = source.mcp_server_id,
            external_name = source.raw_name,
            external_description = source.raw_description,
            input_schema = COALESCE(source.input_schema, '{}'::json),
            output_schema = COALESCE(source.output_schema, '{}'::json),
            required_context = '["store_id"]'::json,
            raw_manifest = COALESCE(source.raw_payload, '{}'::json),
            schema_hash = source.schema_hash,
            sync_status = CASE WHEN source.sync_status = 'synced' THEN 'active' ELSE source.sync_status END,
            last_synced_at = source.last_synced_at,
            publish_status = CASE WHEN agent.status = 'published' AND agent.enabled THEN 'published' ELSE 'draft' END,
            approved_schema_hash = CASE WHEN agent.status = 'published' AND agent.enabled THEN source.schema_hash ELSE NULL END
        FROM mcp_tools AS source
        WHERE source.id = agent.mcp_tool_id
        """
    )
    for column in (
        "provider_id",
        "external_name",
        "input_schema",
        "output_schema",
        "required_context",
        "raw_manifest",
        "schema_hash",
        "sync_status",
        "publish_status",
    ):
        op.alter_column("agent_tools", column, nullable=False)
    op.create_foreign_key(
        "fk_agent_tools_provider_id_tool_providers",
        "agent_tools",
        "tool_providers",
        ["provider_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_agent_tools_provider_external_name",
        "agent_tools",
        ["provider_id", "external_name"],
    )
    op.create_index("ix_agent_tools_provider_id", "agent_tools", ["provider_id"])
    op.create_index("ix_agent_tools_external_name", "agent_tools", ["external_name"])
    op.create_index("ix_agent_tools_schema_hash", "agent_tools", ["schema_hash"])
    op.create_index("ix_agent_tools_sync_status", "agent_tools", ["sync_status"])
    op.create_index("ix_agent_tools_publish_status", "agent_tools", ["publish_status"])
    op.create_index("ix_agent_tools_approved_schema_hash", "agent_tools", ["approved_schema_hash"])

    op.create_table(
        "agent_app_tool_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_app_id", sa.Integer(), nullable=False),
        sa.Column("agent_tool_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_tool_id"], ["agent_tools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_app_id", "agent_tool_id", name="uq_agent_app_tool_grants_app_tool"),
    )
    op.create_index("ix_agent_app_tool_grants_id", "agent_app_tool_grants", ["id"])
    op.create_index("ix_agent_app_tool_grants_project_app_id", "agent_app_tool_grants", ["project_app_id"])
    op.create_index("ix_agent_app_tool_grants_agent_tool_id", "agent_app_tool_grants", ["agent_tool_id"])
    op.execute(
        """
        INSERT INTO agent_app_tool_grants (project_app_id, agent_tool_id, created_at)
        SELECT binding.project_app_id, tool.id, binding.created_at
        FROM agent_app_tool_set_bindings AS binding
        JOIN agent_tools AS tool ON tool.provider_id = binding.mcp_server_id
        WHERE binding.enabled = true
        ON CONFLICT (project_app_id, agent_tool_id) DO NOTHING
        """
    )
    op.drop_table("agent_app_tool_set_bindings")

    op.rename_table("agent_tool_call_logs", "agent_tool_invocations")
    op.alter_column("agent_tool_invocations", "mcp_server_id", new_column_name="provider_id")
    op.alter_column("agent_tool_invocations", "mcp_tool_name", new_column_name="external_name")
    op.alter_column("agent_tool_invocations", "request_payload", new_column_name="request_summary")
    op.alter_column("agent_tool_invocations", "response_payload", new_column_name="response_summary")
    op.add_column("agent_tool_invocations", sa.Column("provider_code", sa.String(length=80), nullable=True))
    op.add_column("agent_tool_invocations", sa.Column("schema_hash", sa.String(length=64), nullable=True))
    op.add_column("agent_tool_invocations", sa.Column("request_id", sa.String(length=100), nullable=True))
    op.add_column("agent_tool_invocations", sa.Column("call_source", sa.String(length=20), server_default="runtime", nullable=False))
    op.add_column("agent_tool_invocations", sa.Column("error_code", sa.String(length=80), nullable=True))
    op.execute(
        """
        UPDATE agent_tool_invocations AS invocation
        SET provider_code = COALESCE(
                (SELECT provider.code FROM tool_providers AS provider WHERE provider.id = invocation.provider_id),
                'unknown'
            ),
            schema_hash = COALESCE(
                (SELECT tool.schema_hash FROM agent_tools AS tool WHERE tool.id = invocation.agent_tool_id),
                ''
            )
        """
    )
    op.execute("UPDATE agent_tool_invocations SET provider_code = 'unknown' WHERE provider_code IS NULL")
    op.execute("UPDATE agent_tool_invocations SET schema_hash = '' WHERE schema_hash IS NULL")
    op.alter_column("agent_tool_invocations", "provider_code", nullable=False)
    op.alter_column("agent_tool_invocations", "schema_hash", nullable=False)
    for old_name in (
        "ix_agent_tool_call_logs_id",
        "ix_agent_tool_call_logs_team_id",
        "ix_agent_tool_call_logs_project_app_id",
        "ix_agent_tool_call_logs_agent_tool_id",
        "ix_agent_tool_call_logs_mcp_server_id",
        "ix_agent_tool_call_logs_session_id",
        "ix_agent_tool_call_logs_trace_id",
        "ix_agent_tool_call_logs_tool_key",
        "ix_agent_tool_call_logs_mcp_tool_name",
        "ix_agent_tool_call_logs_status",
        "ix_agent_tool_call_logs_created_at",
    ):
        op.drop_index(old_name, table_name="agent_tool_invocations")
    for column in (
        "id",
        "team_id",
        "provider_id",
        "agent_tool_id",
        "project_app_id",
        "tool_key",
        "session_id",
        "trace_id",
        "request_id",
        "status",
        "created_at",
    ):
        op.create_index(f"ix_agent_tool_invocations_{column}", "agent_tool_invocations", [column])

    op.drop_constraint("uq_agent_tools_mcp_tool", "agent_tools", type_="unique")
    op.drop_index("ix_agent_tools_mcp_tool_id", table_name="agent_tools")
    op.drop_constraint("agent_tools_mcp_tool_id_fkey", "agent_tools", type_="foreignkey")
    for column in (
        "mcp_tool_id",
        "description",
        "params_schema",
        "response_schema",
        "tool_type",
        "enabled",
        "status",
    ):
        op.drop_column("agent_tools", column)
    op.drop_table("mcp_tools")


def downgrade() -> None:
    raise RuntimeError("Tool provider unification cannot be downgraded without losing governance data")
