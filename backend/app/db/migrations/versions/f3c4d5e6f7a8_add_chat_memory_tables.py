"""add chat memory tables

Revision ID: f3c4d5e6f7a8
Revises: f2b3c4d5e6f7
Create Date: 2026-04-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "f3c4d5e6f7a8"
down_revision: Union[str, None] = "f2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, name: str) -> bool:
    return name in inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "chat_sessions"):
        op.create_table(
            "chat_sessions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("knowledge_base_id", sa.Integer(), nullable=True),
            sa.Column("category_id", sa.Integer(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["knowledge_base_id"],
                ["knowledge_bases.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["category_id"],
                ["document_categories.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "session_id",
                name="uq_chat_sessions_user_session_id",
            ),
        )
        op.create_index("ix_chat_sessions_session_id", "chat_sessions", ["session_id"])
        op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
        op.create_index(
            "ix_chat_sessions_knowledge_base_id",
            "chat_sessions",
            ["knowledge_base_id"],
        )
        op.create_index("ix_chat_sessions_category_id", "chat_sessions", ["category_id"])

    if not _table_exists(conn, "chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("chat_session_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(
                ["chat_session_id"],
                ["chat_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_chat_messages_chat_session_id",
            "chat_messages",
            ["chat_session_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "chat_messages"):
        op.drop_index("ix_chat_messages_chat_session_id", table_name="chat_messages")
        op.drop_table("chat_messages")

    if _table_exists(conn, "chat_sessions"):
        op.drop_index("ix_chat_sessions_category_id", table_name="chat_sessions")
        op.drop_index("ix_chat_sessions_knowledge_base_id", table_name="chat_sessions")
        op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
        op.drop_index("ix_chat_sessions_session_id", table_name="chat_sessions")
        op.drop_table("chat_sessions")
