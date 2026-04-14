"""add document categories and document category/source_path fields

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-04-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, name: str) -> bool:
    return name in inspect(conn).get_table_names()


def _documents_has_column(conn, col_name: str) -> bool:
    if "documents" not in inspect(conn).get_table_names():
        return False
    cols = [c["name"] for c in inspect(conn).get_columns("documents")]
    return col_name in cols


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "document_categories"):
        op.create_table(
            "document_categories",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_document_categories_knowledge_base_id",
            "document_categories",
            ["knowledge_base_id"],
        )

    if not _documents_has_column(conn, "category_id"):
        op.add_column("documents", sa.Column("category_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_documents_category_id",
            "documents",
            "document_categories",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_documents_category_id", "documents", ["category_id"])

    if not _documents_has_column(conn, "source_path"):
        op.add_column("documents", sa.Column("source_path", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()

    if _documents_has_column(conn, "source_path"):
        op.drop_column("documents", "source_path")

    if _documents_has_column(conn, "category_id"):
        op.drop_index("ix_documents_category_id", table_name="documents")
        op.drop_constraint("fk_documents_category_id", "documents", type_="foreignkey")
        op.drop_column("documents", "category_id")

    if _table_exists(conn, "document_categories"):
        op.drop_index(
            "ix_document_categories_knowledge_base_id",
            table_name="document_categories",
        )
        op.drop_table("document_categories")
