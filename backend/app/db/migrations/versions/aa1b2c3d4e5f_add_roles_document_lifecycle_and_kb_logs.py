"""add roles, document lifecycle fields, and kb chat logs

Revision ID: aa1b2c3d4e5f
Revises: f7a8b9c0d1e2
Create Date: 2026-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "aa1b2c3d4e5f"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
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

    if _table_exists(conn, "users") and not _has_column(conn, "users", "role"):
        op.add_column(
            "users",
            sa.Column("role", sa.String(length=30), nullable=False, server_default="end_user"),
        )
        op.create_index("ix_users_role", "users", ["role"], unique=False)
        conn.execute(sa.text("UPDATE users SET role = 'kb_admin' WHERE username = 'admin'"))
        op.alter_column("users", "role", server_default=None)

    if _table_exists(conn, "documents"):
        if not _has_column(conn, "documents", "status"):
            op.add_column(
                "documents",
                sa.Column("status", sa.String(length=20), nullable=False, server_default="published"),
            )
            op.create_index("ix_documents_status", "documents", ["status"], unique=False)
            op.alter_column("documents", "status", server_default=None)
        if not _has_column(conn, "documents", "published_at"):
            op.add_column("documents", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column(conn, "documents", "published_by"):
            op.add_column("documents", sa.Column("published_by", sa.Integer(), nullable=True))
            op.create_index("ix_documents_published_by", "documents", ["published_by"], unique=False)
            op.create_foreign_key(
                "fk_documents_published_by_users",
                "documents",
                "users",
                ["published_by"],
                ["id"],
                ondelete="SET NULL",
            )
        if not _has_column(conn, "documents", "reviewed_at"):
            op.add_column("documents", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column(conn, "documents", "reviewed_by"):
            op.add_column("documents", sa.Column("reviewed_by", sa.Integer(), nullable=True))
            op.create_index("ix_documents_reviewed_by", "documents", ["reviewed_by"], unique=False)
            op.create_foreign_key(
                "fk_documents_reviewed_by_users",
                "documents",
                "users",
                ["reviewed_by"],
                ["id"],
                ondelete="SET NULL",
            )

    if not _table_exists(conn, "kb_chat_logs"):
        op.create_table(
            "kb_chat_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("knowledge_base_id", sa.Integer(), nullable=True),
            sa.Column("category_id", sa.Integer(), nullable=True),
            sa.Column("query", sa.Text(), nullable=False),
            sa.Column("answer_text", sa.Text(), nullable=False),
            sa.Column("answer_status", sa.String(length=20), nullable=False, server_default="answered"),
            sa.Column("retrieval_status", sa.String(length=30), nullable=True),
            sa.Column("retrieved_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("feedback_value", sa.String(length=20), nullable=True),
            sa.Column("feedback_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["category_id"], ["document_categories.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_kb_chat_logs_user_id", "kb_chat_logs", ["user_id"], unique=False)
        op.create_index("ix_kb_chat_logs_session_id", "kb_chat_logs", ["session_id"], unique=False)
        op.create_index("ix_kb_chat_logs_knowledge_base_id", "kb_chat_logs", ["knowledge_base_id"], unique=False)
        op.create_index("ix_kb_chat_logs_category_id", "kb_chat_logs", ["category_id"], unique=False)
        op.create_index("ix_kb_chat_logs_answer_status", "kb_chat_logs", ["answer_status"], unique=False)
        op.create_index("ix_kb_chat_logs_retrieval_status", "kb_chat_logs", ["retrieval_status"], unique=False)
        op.create_index("ix_kb_chat_logs_feedback_value", "kb_chat_logs", ["feedback_value"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "kb_chat_logs"):
        op.drop_index("ix_kb_chat_logs_feedback_value", table_name="kb_chat_logs")
        op.drop_index("ix_kb_chat_logs_retrieval_status", table_name="kb_chat_logs")
        op.drop_index("ix_kb_chat_logs_answer_status", table_name="kb_chat_logs")
        op.drop_index("ix_kb_chat_logs_category_id", table_name="kb_chat_logs")
        op.drop_index("ix_kb_chat_logs_knowledge_base_id", table_name="kb_chat_logs")
        op.drop_index("ix_kb_chat_logs_session_id", table_name="kb_chat_logs")
        op.drop_index("ix_kb_chat_logs_user_id", table_name="kb_chat_logs")
        op.drop_table("kb_chat_logs")

    if _table_exists(conn, "documents"):
        inspector = inspect(conn)
        fk_names = {item.get("name") for item in inspector.get_foreign_keys("documents") if item.get("name")}
        if "fk_documents_reviewed_by_users" in fk_names:
            op.drop_constraint("fk_documents_reviewed_by_users", "documents", type_="foreignkey")
        if "fk_documents_published_by_users" in fk_names:
            op.drop_constraint("fk_documents_published_by_users", "documents", type_="foreignkey")
        if _has_column(conn, "documents", "reviewed_by"):
            op.drop_index("ix_documents_reviewed_by", table_name="documents")
            op.drop_column("documents", "reviewed_by")
        if _has_column(conn, "documents", "reviewed_at"):
            op.drop_column("documents", "reviewed_at")
        if _has_column(conn, "documents", "published_by"):
            op.drop_index("ix_documents_published_by", table_name="documents")
            op.drop_column("documents", "published_by")
        if _has_column(conn, "documents", "published_at"):
            op.drop_column("documents", "published_at")
        if _has_column(conn, "documents", "status"):
            op.drop_index("ix_documents_status", table_name="documents")
            op.drop_column("documents", "status")

    if _table_exists(conn, "users") and _has_column(conn, "users", "role"):
        op.drop_index("ix_users_role", table_name="users")
        op.drop_column("users", "role")
