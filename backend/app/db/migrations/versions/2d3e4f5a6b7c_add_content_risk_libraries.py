"""add content risk libraries

Revision ID: 2d3e4f5a6b7c
Revises: ab1c2d3e4f5a
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "2d3e4f5a6b7c"
down_revision = "ab1c2d3e4f5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_risk_libraries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rule_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reference_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_risk_libraries_id", "content_risk_libraries", ["id"], unique=False)
    op.create_index("ix_content_risk_libraries_name", "content_risk_libraries", ["name"], unique=False)
    op.create_index(
        "ix_content_risk_libraries_enabled",
        "content_risk_libraries",
        ["enabled"],
        unique=False,
    )
    op.create_index(
        "ix_content_risk_libraries_created_by_user_id",
        "content_risk_libraries",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_content_risk_libraries_updated_by_user_id",
        "content_risk_libraries",
        ["updated_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_content_risk_libraries_updated_by_user_id", table_name="content_risk_libraries")
    op.drop_index("ix_content_risk_libraries_created_by_user_id", table_name="content_risk_libraries")
    op.drop_index("ix_content_risk_libraries_enabled", table_name="content_risk_libraries")
    op.drop_index("ix_content_risk_libraries_name", table_name="content_risk_libraries")
    op.drop_index("ix_content_risk_libraries_id", table_name="content_risk_libraries")
    op.drop_table("content_risk_libraries")
