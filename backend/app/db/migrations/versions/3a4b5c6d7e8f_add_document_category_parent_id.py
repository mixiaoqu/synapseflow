"""add document_category parent_id for nested folders

Revision ID: 3a4b5c6d7e8f
Revises: 2c3d4e5f6a7b
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa


revision = "3a4b5c6d7e8f"
down_revision = "2c3d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_categories",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_categories_parent_id",
        "document_categories",
        "document_categories",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_document_categories_parent_id",
        "document_categories",
        ["parent_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_categories_parent_id", table_name="document_categories")
    op.drop_constraint("fk_document_categories_parent_id", "document_categories", type_="foreignkey")
    op.drop_column("document_categories", "parent_id")
