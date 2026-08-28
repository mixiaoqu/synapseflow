"""drop stale kb chat log diagnostic columns

Revision ID: 3e5f7a9b1c2d
Revises: 2d4e6f8a9b0c
Create Date: 2026-06-12 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "3e5f7a9b1c2d"
down_revision: Union[str, None] = "2d4e6f8a9b0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def _drop_column_if_exists(conn, table_name: str, column_name: str) -> None:
    if _has_column(conn, table_name, column_name):
        op.drop_column(table_name, column_name)


def _add_column_if_missing(conn, table_name: str, column: sa.Column) -> None:
    if not _has_column(conn, table_name, str(column.name)):
        op.add_column(table_name, column)


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "kb_chat_logs"):
        return

    for column_name in (
        "semantic_query_count",
        "lexical_term_count",
        "reranked_candidate_count",
        "graph_used",
        "merge_latency_ms",
    ):
        _drop_column_if_exists(conn, "kb_chat_logs", column_name)


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "kb_chat_logs"):
        return

    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("semantic_query_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("lexical_term_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("reranked_candidate_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("graph_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(
        conn,
        "kb_chat_logs",
        sa.Column("merge_latency_ms", sa.Integer(), nullable=True),
    )

    for column_name in (
        "semantic_query_count",
        "lexical_term_count",
        "reranked_candidate_count",
        "graph_used",
    ):
        op.alter_column("kb_chat_logs", column_name, server_default=None)
