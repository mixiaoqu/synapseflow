"""add projects, project applications, and embedded chat context

Revision ID: fc3d4e5f6a7b
Revises: fb2c3d4e5f6
Create Date: 2026-04-23 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "fc3d4e5f6a7b"
down_revision: Union[str, None] = "fb2c3d4e5f6"
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


def _has_unique(conn, table_name: str, name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return name in {item["name"] for item in inspect(conn).get_unique_constraints(table_name)}


def _has_fk(conn, table_name: str, fk_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return fk_name in {item["name"] for item in inspect(conn).get_foreign_keys(table_name)}


def _add_context_columns(conn, table_name: str) -> None:
    if not _has_column(conn, table_name, "project_id"):
        op.add_column(table_name, sa.Column("project_id", sa.Integer(), nullable=True))
    if not _has_column(conn, table_name, "project_app_id"):
        op.add_column(table_name, sa.Column("project_app_id", sa.Integer(), nullable=True))
    if not _has_column(conn, table_name, "external_user_id"):
        op.add_column(table_name, sa.Column("external_user_id", sa.String(length=255), nullable=True))
    if not _has_column(conn, table_name, "external_user_name"):
        op.add_column(table_name, sa.Column("external_user_name", sa.String(length=255), nullable=True))
    if not _has_column(conn, table_name, "source"):
        op.add_column(table_name, sa.Column("source", sa.String(length=80), nullable=True))

    for column in ("project_id", "project_app_id", "external_user_id", "source"):
        index_name = f"ix_{table_name}_{column}"
        if not _has_index(conn, table_name, index_name):
            op.create_index(index_name, table_name, [column], unique=False)

    project_fk = f"fk_{table_name}_project_id_projects"
    if not _has_fk(conn, table_name, project_fk):
        op.create_foreign_key(
            project_fk,
            table_name,
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )

    project_app_fk = f"fk_{table_name}_project_app_id_project_apps"
    if not _has_fk(conn, table_name, project_app_fk):
        op.create_foreign_key(
            project_app_fk,
            table_name,
            "project_apps",
            ["project_app_id"],
            ["id"],
            ondelete="SET NULL",
        )


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "projects"):
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("code", name="uq_projects_code"),
        )
    if not _has_index(conn, "projects", "ix_projects_team_id"):
        op.create_index("ix_projects_team_id", "projects", ["team_id"], unique=False)
    if not _has_index(conn, "projects", "ix_projects_code"):
        op.create_index("ix_projects_code", "projects", ["code"], unique=True)
    if not _has_index(conn, "projects", "ix_projects_is_active"):
        op.create_index("ix_projects_is_active", "projects", ["is_active"], unique=False)

    if not _table_exists(conn, "project_apps"):
        op.create_table(
            "project_apps",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("default_assistant_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["default_assistant_id"],
                ["assistant_profiles.id"],
                ondelete="SET NULL",
            ),
            sa.UniqueConstraint("project_id", "code", name="uq_project_apps_project_code"),
        )
    if not _has_index(conn, "project_apps", "ix_project_apps_project_id"):
        op.create_index("ix_project_apps_project_id", "project_apps", ["project_id"], unique=False)
    if not _has_index(conn, "project_apps", "ix_project_apps_code"):
        op.create_index("ix_project_apps_code", "project_apps", ["code"], unique=False)
    if not _has_index(conn, "project_apps", "ix_project_apps_default_assistant_id"):
        op.create_index(
            "ix_project_apps_default_assistant_id",
            "project_apps",
            ["default_assistant_id"],
            unique=False,
        )
    if not _has_index(conn, "project_apps", "ix_project_apps_is_active"):
        op.create_index("ix_project_apps_is_active", "project_apps", ["is_active"], unique=False)

    if _table_exists(conn, "chat_sessions"):
        op.alter_column("chat_sessions", "user_id", existing_type=sa.Integer(), nullable=True)
        _add_context_columns(conn, "chat_sessions")
        if not _has_unique(conn, "chat_sessions", "uq_chat_sessions_project_app_external_session"):
            op.create_unique_constraint(
                "uq_chat_sessions_project_app_external_session",
                "chat_sessions",
                ["project_app_id", "external_user_id", "session_id"],
            )

    if _table_exists(conn, "kb_chat_logs"):
        op.alter_column("kb_chat_logs", "user_id", existing_type=sa.Integer(), nullable=True)
        _add_context_columns(conn, "kb_chat_logs")


def downgrade() -> None:
    conn = op.get_bind()

    for table_name in ("kb_chat_logs", "chat_sessions"):
        if not _table_exists(conn, table_name):
            continue
        if table_name == "chat_sessions" and _has_unique(
            conn,
            table_name,
            "uq_chat_sessions_project_app_external_session",
        ):
            op.drop_constraint(
                "uq_chat_sessions_project_app_external_session",
                table_name,
                type_="unique",
            )
        for fk_name in (
            f"fk_{table_name}_project_app_id_project_apps",
            f"fk_{table_name}_project_id_projects",
        ):
            if _has_fk(conn, table_name, fk_name):
                op.drop_constraint(fk_name, table_name, type_="foreignkey")
        for column in ("source", "external_user_id", "project_app_id", "project_id"):
            index_name = f"ix_{table_name}_{column}"
            if _has_index(conn, table_name, index_name):
                op.drop_index(index_name, table_name=table_name)
        for column in (
            "source",
            "external_user_name",
            "external_user_id",
            "project_app_id",
            "project_id",
        ):
            if _has_column(conn, table_name, column):
                op.drop_column(table_name, column)
        op.alter_column(table_name, "user_id", existing_type=sa.Integer(), nullable=False)

    if _table_exists(conn, "project_apps"):
        op.drop_table("project_apps")
    if _table_exists(conn, "projects"):
        op.drop_table("projects")
