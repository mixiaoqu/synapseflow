"""add collections and document collection_id

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
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
    if not _table_exists(conn, "collections"):
        op.create_table(
            "collections",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _documents_has_column(conn, "collection_id"):
        op.add_column("documents", sa.Column("collection_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_documents_collection_id",
            "documents",
            "collections",
            ["collection_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_documents_collection_id", "documents", ["collection_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if _documents_has_column(conn, "collection_id"):
        op.drop_index("ix_documents_collection_id", table_name="documents")
        op.drop_constraint("fk_documents_collection_id", "documents", type_="foreignkey")
        op.drop_column("documents", "collection_id")
    if _table_exists(conn, "collections"):
        op.drop_table("collections")
