"""Replace per-tool app bindings with MCP tool-set bindings.

Revision ID: gh9c0d1e2f3a
Revises: fg8b9c0d1e2f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "gh9c0d1e2f3a"
down_revision: Union[str, Sequence[str], None] = "fg8b9c0d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("agent_app_tool_bindings")
    op.create_table(
        "agent_app_tool_set_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_app_id", sa.Integer(), nullable=False),
        sa.Column("mcp_server_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["mcp_server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_app_id",
            "mcp_server_id",
            name="uq_agent_app_tool_set_bindings_app_server",
        ),
    )
    op.create_index(
        op.f("ix_agent_app_tool_set_bindings_id"),
        "agent_app_tool_set_bindings",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_app_tool_set_bindings_project_app_id"),
        "agent_app_tool_set_bindings",
        ["project_app_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_app_tool_set_bindings_mcp_server_id"),
        "agent_app_tool_set_bindings",
        ["mcp_server_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_app_tool_set_bindings_enabled"),
        "agent_app_tool_set_bindings",
        ["enabled"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("agent_app_tool_set_bindings")
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
