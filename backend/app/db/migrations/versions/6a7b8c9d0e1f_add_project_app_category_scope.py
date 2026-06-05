"""add project app category scope

Revision ID: 6a7b8c9d0e1f
Revises: 5e6f7a8b9c0d
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "6a7b8c9d0e1f"
down_revision = "5e6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_apps",
        sa.Column("category_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_apps_category_id",
        "project_apps",
        "document_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_project_apps_category_id",
        "project_apps",
        ["category_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_apps_category_id", table_name="project_apps")
    op.drop_constraint("fk_project_apps_category_id", "project_apps", type_="foreignkey")
    op.drop_column("project_apps", "category_id")
