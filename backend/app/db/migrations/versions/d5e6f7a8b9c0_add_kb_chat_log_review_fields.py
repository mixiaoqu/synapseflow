"""add review fields to kb chat logs

Revision ID: d5e6f7a8b9c0
Revises: c2d3e4f5a6b7
Create Date: 2026-04-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {item["name"] for item in inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "kb_chat_logs"):
        if not _has_column(conn, "kb_chat_logs", "review_label"):
            op.add_column("kb_chat_logs", sa.Column("review_label", sa.String(length=40), nullable=True))
            op.create_index("ix_kb_chat_logs_review_label", "kb_chat_logs", ["review_label"], unique=False)
        if not _has_column(conn, "kb_chat_logs", "review_note"):
            op.add_column("kb_chat_logs", sa.Column("review_note", sa.Text(), nullable=True))
        if not _has_column(conn, "kb_chat_logs", "reviewed_at"):
            op.add_column("kb_chat_logs", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column(conn, "kb_chat_logs", "reviewed_by_user_id"):
            op.add_column("kb_chat_logs", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
            op.create_index(
                "ix_kb_chat_logs_reviewed_by_user_id",
                "kb_chat_logs",
                ["reviewed_by_user_id"],
                unique=False,
            )
            op.create_foreign_key(
                "fk_kb_chat_logs_reviewed_by_user_id_users",
                "kb_chat_logs",
                "users",
                ["reviewed_by_user_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "kb_chat_logs"):
        fk_names = {
            item.get("name")
            for item in inspect(conn).get_foreign_keys("kb_chat_logs")
            if item.get("name")
        }
        if "fk_kb_chat_logs_reviewed_by_user_id_users" in fk_names:
            op.drop_constraint(
                "fk_kb_chat_logs_reviewed_by_user_id_users",
                "kb_chat_logs",
                type_="foreignkey",
            )
        if _has_column(conn, "kb_chat_logs", "reviewed_by_user_id"):
            op.drop_index("ix_kb_chat_logs_reviewed_by_user_id", table_name="kb_chat_logs")
            op.drop_column("kb_chat_logs", "reviewed_by_user_id")
        if _has_column(conn, "kb_chat_logs", "reviewed_at"):
            op.drop_column("kb_chat_logs", "reviewed_at")
        if _has_column(conn, "kb_chat_logs", "review_note"):
            op.drop_column("kb_chat_logs", "review_note")
        if _has_column(conn, "kb_chat_logs", "review_label"):
            op.drop_index("ix_kb_chat_logs_review_label", table_name="kb_chat_logs")
            op.drop_column("kb_chat_logs", "review_label")
