"""add chat session summary fields

Revision ID: 1c2d3e4f5a6b
Revises: 0b1c2d3e4f5a
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "1c2d3e4f5a6b"
down_revision: Union[str, None] = "0b1c2d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "chat_sessions"):
        return

    if not _has_column(conn, "chat_sessions", "title"):
        op.add_column("chat_sessions", sa.Column("title", sa.String(length=255), nullable=True))
    if not _has_column(conn, "chat_sessions", "preview"):
        op.add_column("chat_sessions", sa.Column("preview", sa.Text(), nullable=True))
    if not _has_column(conn, "chat_sessions", "message_count"):
        op.add_column(
            "chat_sessions",
            sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column("chat_sessions", "message_count", server_default=None)

    if _table_exists(conn, "chat_messages"):
        conn.execute(
            text(
                """
                UPDATE chat_sessions AS cs
                SET
                    message_count = COALESCE((
                        SELECT COUNT(*)
                        FROM chat_messages AS cm
                        WHERE cm.chat_session_id = cs.id
                    ), 0),
                    title = COALESCE(
                        NULLIF(cs.title, ''),
                        (
                            SELECT SUBSTRING(REGEXP_REPLACE(cm.content, '\\s+', ' ', 'g') FROM 1 FOR 60)
                            FROM chat_messages AS cm
                            WHERE cm.chat_session_id = cs.id
                                AND LOWER(cm.role) = 'user'
                                AND BTRIM(cm.content) <> ''
                            ORDER BY cm.created_at ASC, cm.id ASC
                            LIMIT 1
                        ),
                        (
                            SELECT SUBSTRING(REGEXP_REPLACE(cm.content, '\\s+', ' ', 'g') FROM 1 FOR 60)
                            FROM chat_messages AS cm
                            WHERE cm.chat_session_id = cs.id
                                AND BTRIM(cm.content) <> ''
                            ORDER BY cm.created_at ASC, cm.id ASC
                            LIMIT 1
                        )
                    ),
                    preview = COALESCE(
                        (
                            SELECT SUBSTRING(REGEXP_REPLACE(cm.content, '\\s+', ' ', 'g') FROM 1 FOR 120)
                            FROM chat_messages AS cm
                            WHERE cm.chat_session_id = cs.id
                                AND BTRIM(cm.content) <> ''
                            ORDER BY cm.created_at DESC, cm.id DESC
                            LIMIT 1
                        ),
                        cs.preview
                    )
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "chat_sessions"):
        return

    if _has_column(conn, "chat_sessions", "message_count"):
        op.drop_column("chat_sessions", "message_count")
    if _has_column(conn, "chat_sessions", "preview"):
        op.drop_column("chat_sessions", "preview")
    if _has_column(conn, "chat_sessions", "title"):
        op.drop_column("chat_sessions", "title")
