"""add document upload sessions

Revision ID: 0c1d2e3f4a5b
Revises: 4e6f8a0b2c3d
Create Date: 2026-06-21 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0c1d2e3f4a5b"
down_revision: Union[str, None] = "4e6f8a0b2c3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return index_name in {index["name"] for index in inspect(conn).get_indexes(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "document_upload_sessions"):
        return

    op.create_table(
        "document_upload_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "knowledge_base_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("document_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=True),
        sa.Column("bucket_name", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="initialized"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    for index_name, columns in (
        ("ix_document_upload_sessions_user_id", ["user_id"]),
        ("ix_document_upload_sessions_team_id", ["team_id"]),
        ("ix_document_upload_sessions_knowledge_base_id", ["knowledge_base_id"]),
        ("ix_document_upload_sessions_category_id", ["category_id"]),
        ("ix_document_upload_sessions_status", ["status"]),
        ("ix_document_upload_sessions_expires_at", ["expires_at"]),
    ):
        if not _index_exists(conn, "document_upload_sessions", index_name):
            op.create_index(index_name, "document_upload_sessions", columns)

    op.alter_column("document_upload_sessions", "file_size", server_default=None)
    op.alter_column("document_upload_sessions", "status", server_default=None)


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "document_upload_sessions"):
        return

    for index_name in (
        "ix_document_upload_sessions_expires_at",
        "ix_document_upload_sessions_status",
        "ix_document_upload_sessions_category_id",
        "ix_document_upload_sessions_knowledge_base_id",
        "ix_document_upload_sessions_team_id",
        "ix_document_upload_sessions_user_id",
    ):
        if _index_exists(conn, "document_upload_sessions", index_name):
            op.drop_index(index_name, table_name="document_upload_sessions")

    op.drop_table("document_upload_sessions")
