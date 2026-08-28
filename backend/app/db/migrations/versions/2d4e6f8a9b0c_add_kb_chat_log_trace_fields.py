"""add kb chat log trace fields

Revision ID: 2d4e6f8a9b0c
Revises: 1c2d3e4f5a6b
Create Date: 2026-06-11 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "2d4e6f8a9b0c"
down_revision: Union[str, None] = "1c2d3e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def _add_column_if_missing(conn, table_name: str, column: sa.Column) -> None:
    if not _has_column(conn, table_name, str(column.name)):
        op.add_column(table_name, column)


def _drop_column_if_exists(conn, table_name: str, column_name: str) -> None:
    if _has_column(conn, table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "kb_chat_logs"):
        return

    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("text_hit_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("graph_hit_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("merged_candidate_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("final_context_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("empty_reason", sa.String(length=40), nullable=True),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("rerank_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("trace_payload", sa.JSON(), nullable=True),
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kb_chat_logs_empty_reason
        ON kb_chat_logs (empty_reason);
        """
    )
    _drop_column_if_exists(conn, "kb_chat_logs", "retrieved_count")

    for column_name in (
        "text_hit_count",
        "graph_hit_count",
        "merged_candidate_count",
        "final_context_count",
        "rerank_enabled",
    ):
        op.alter_column("kb_chat_logs", column_name, server_default=None)


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "kb_chat_logs"):
        return

    op.execute("DROP INDEX IF EXISTS ix_kb_chat_logs_empty_reason")
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("retrieved_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("kb_chat_logs", "retrieved_count", server_default=None)

    for column_name in (
        "trace_payload",
        "rerank_enabled",
        "empty_reason",
        "final_context_count",
        "merged_candidate_count",
        "graph_hit_count",
        "text_hit_count",
    ):
        if _has_column(conn, "kb_chat_logs", column_name):
            op.drop_column("kb_chat_logs", column_name)
