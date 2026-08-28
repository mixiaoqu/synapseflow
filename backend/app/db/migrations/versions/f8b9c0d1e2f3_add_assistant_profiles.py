"""add assistant profiles and assistant references

Revision ID: f8b9c0d1e2f3
Revises: e1f2a3b4c5d6
Create Date: 2026-04-15 21:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f8b9c0d1e2f3"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
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

    if not _table_exists(conn, "assistant_profiles"):
        op.create_table(
            "assistant_profiles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("slug", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("welcome_message", sa.Text(), nullable=True),
            sa.Column("placeholder_text", sa.String(length=255), nullable=True),
            sa.Column("persona_prompt", sa.Text(), nullable=True),
            sa.Column("rule_template", sa.Text(), nullable=True),
            sa.Column(
                "suggested_prompts",
                postgresql.JSON(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["knowledge_base_id"],
                ["knowledge_bases.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["category_id"],
                ["document_categories.id"],
                ondelete="SET NULL",
            ),
        )

    if not _has_index(conn, "assistant_profiles", "ix_assistant_profiles_team_id"):
        op.create_index("ix_assistant_profiles_team_id", "assistant_profiles", ["team_id"], unique=False)
    if not _has_index(conn, "assistant_profiles", "ix_assistant_profiles_knowledge_base_id"):
        op.create_index(
            "ix_assistant_profiles_knowledge_base_id",
            "assistant_profiles",
            ["knowledge_base_id"],
            unique=False,
        )
    if not _has_index(conn, "assistant_profiles", "ix_assistant_profiles_category_id"):
        op.create_index(
            "ix_assistant_profiles_category_id",
            "assistant_profiles",
            ["category_id"],
            unique=False,
        )
    if not _has_index(conn, "assistant_profiles", "ix_assistant_profiles_slug"):
        op.create_index("ix_assistant_profiles_slug", "assistant_profiles", ["slug"], unique=True)
    if not _has_index(conn, "assistant_profiles", "ix_assistant_profiles_is_active"):
        op.create_index(
            "ix_assistant_profiles_is_active",
            "assistant_profiles",
            ["is_active"],
            unique=False,
        )
    if not _has_index(conn, "assistant_profiles", "ix_assistant_profiles_sort_order"):
        op.create_index(
            "ix_assistant_profiles_sort_order",
            "assistant_profiles",
            ["sort_order"],
            unique=False,
        )

    if _table_exists(conn, "chat_sessions") and not _has_column(conn, "chat_sessions", "assistant_id"):
        op.add_column("chat_sessions", sa.Column("assistant_id", sa.Integer(), nullable=True))
    if _table_exists(conn, "chat_sessions") and not _has_index(conn, "chat_sessions", "ix_chat_sessions_assistant_id"):
        op.create_index("ix_chat_sessions_assistant_id", "chat_sessions", ["assistant_id"], unique=False)
    if _table_exists(conn, "chat_sessions") and not _has_fk(conn, "chat_sessions", "fk_chat_sessions_assistant_id_assistant_profiles"):
        op.create_foreign_key(
            "fk_chat_sessions_assistant_id_assistant_profiles",
            "chat_sessions",
            "assistant_profiles",
            ["assistant_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if _table_exists(conn, "kb_chat_logs") and not _has_column(conn, "kb_chat_logs", "assistant_id"):
        op.add_column("kb_chat_logs", sa.Column("assistant_id", sa.Integer(), nullable=True))
    if _table_exists(conn, "kb_chat_logs") and not _has_index(conn, "kb_chat_logs", "ix_kb_chat_logs_assistant_id"):
        op.create_index("ix_kb_chat_logs_assistant_id", "kb_chat_logs", ["assistant_id"], unique=False)
    if _table_exists(conn, "kb_chat_logs") and not _has_fk(conn, "kb_chat_logs", "fk_kb_chat_logs_assistant_id_assistant_profiles"):
        op.create_foreign_key(
            "fk_kb_chat_logs_assistant_id_assistant_profiles",
            "kb_chat_logs",
            "assistant_profiles",
            ["assistant_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "kb_chat_logs"):
        if _has_fk(conn, "kb_chat_logs", "fk_kb_chat_logs_assistant_id_assistant_profiles"):
            op.drop_constraint(
                "fk_kb_chat_logs_assistant_id_assistant_profiles",
                "kb_chat_logs",
                type_="foreignkey",
            )
        if _has_index(conn, "kb_chat_logs", "ix_kb_chat_logs_assistant_id"):
            op.drop_index("ix_kb_chat_logs_assistant_id", table_name="kb_chat_logs")
        if _has_column(conn, "kb_chat_logs", "assistant_id"):
            op.drop_column("kb_chat_logs", "assistant_id")

    if _table_exists(conn, "chat_sessions"):
        if _has_fk(conn, "chat_sessions", "fk_chat_sessions_assistant_id_assistant_profiles"):
            op.drop_constraint(
                "fk_chat_sessions_assistant_id_assistant_profiles",
                "chat_sessions",
                type_="foreignkey",
            )
        if _has_index(conn, "chat_sessions", "ix_chat_sessions_assistant_id"):
            op.drop_index("ix_chat_sessions_assistant_id", table_name="chat_sessions")
        if _has_column(conn, "chat_sessions", "assistant_id"):
            op.drop_column("chat_sessions", "assistant_id")

    if _table_exists(conn, "assistant_profiles"):
        if _has_index(conn, "assistant_profiles", "ix_assistant_profiles_sort_order"):
            op.drop_index("ix_assistant_profiles_sort_order", table_name="assistant_profiles")
        if _has_index(conn, "assistant_profiles", "ix_assistant_profiles_is_active"):
            op.drop_index("ix_assistant_profiles_is_active", table_name="assistant_profiles")
        if _has_index(conn, "assistant_profiles", "ix_assistant_profiles_slug"):
            op.drop_index("ix_assistant_profiles_slug", table_name="assistant_profiles")
        if _has_index(conn, "assistant_profiles", "ix_assistant_profiles_category_id"):
            op.drop_index("ix_assistant_profiles_category_id", table_name="assistant_profiles")
        if _has_index(conn, "assistant_profiles", "ix_assistant_profiles_knowledge_base_id"):
            op.drop_index("ix_assistant_profiles_knowledge_base_id", table_name="assistant_profiles")
        if _has_index(conn, "assistant_profiles", "ix_assistant_profiles_team_id"):
            op.drop_index("ix_assistant_profiles_team_id", table_name="assistant_profiles")
        op.drop_table("assistant_profiles")
