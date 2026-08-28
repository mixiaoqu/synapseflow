"""Add business tools."""

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "2e3f4a5b6c7d"
down_revision: Union[str, None] = "1d2e3f4a5b6c"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
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
    op.create_index(op.f("ix_business_tools_enabled"), "business_tools", ["enabled"], unique=False)
    op.create_index(op.f("ix_business_tools_id"), "business_tools", ["id"], unique=False)
    op.create_index(op.f("ix_business_tools_team_id"), "business_tools", ["team_id"], unique=False)
    op.create_index(op.f("ix_business_tools_tool_key"), "business_tools", ["tool_key"], unique=False)

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
    op.create_index(
        op.f("ix_project_app_business_tool_bindings_business_tool_id"),
        "project_app_business_tool_bindings",
        ["business_tool_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_app_business_tool_bindings_enabled"),
        "project_app_business_tool_bindings",
        ["enabled"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_app_business_tool_bindings_id"),
        "project_app_business_tool_bindings",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_app_business_tool_bindings_project_app_id"),
        "project_app_business_tool_bindings",
        ["project_app_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_project_app_business_tool_bindings_project_app_id"),
        table_name="project_app_business_tool_bindings",
    )
    op.drop_index(
        op.f("ix_project_app_business_tool_bindings_id"),
        table_name="project_app_business_tool_bindings",
    )
    op.drop_index(
        op.f("ix_project_app_business_tool_bindings_enabled"),
        table_name="project_app_business_tool_bindings",
    )
    op.drop_index(
        op.f("ix_project_app_business_tool_bindings_business_tool_id"),
        table_name="project_app_business_tool_bindings",
    )
    op.drop_table("project_app_business_tool_bindings")

    op.drop_index(op.f("ix_business_tools_tool_key"), table_name="business_tools")
    op.drop_index(op.f("ix_business_tools_team_id"), table_name="business_tools")
    op.drop_index(op.f("ix_business_tools_id"), table_name="business_tools")
    op.drop_index(op.f("ix_business_tools_enabled"), table_name="business_tools")
    op.drop_table("business_tools")
