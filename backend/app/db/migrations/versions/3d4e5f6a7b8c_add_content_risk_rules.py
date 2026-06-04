"""add content risk rules

Revision ID: 3d4e5f6a7b8c
Revises: 2d3e4f5a6b7c
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "3d4e5f6a7b8c"
down_revision = "2d3e4f5a6b7c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_risk_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("library_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule_type", sa.String(length=30), nullable=False),
        sa.Column("match_mode", sa.String(length=30), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("risk_category", sa.String(length=50), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("default_action", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["library_id"], ["content_risk_libraries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("library_id", "name", name="uq_content_risk_rules_library_name"),
    )
    op.create_index("ix_content_risk_rules_id", "content_risk_rules", ["id"], unique=False)
    op.create_index("ix_content_risk_rules_library_id", "content_risk_rules", ["library_id"], unique=False)
    op.create_index("ix_content_risk_rules_name", "content_risk_rules", ["name"], unique=False)
    op.create_index("ix_content_risk_rules_rule_type", "content_risk_rules", ["rule_type"], unique=False)
    op.create_index("ix_content_risk_rules_match_mode", "content_risk_rules", ["match_mode"], unique=False)
    op.create_index(
        "ix_content_risk_rules_risk_category",
        "content_risk_rules",
        ["risk_category"],
        unique=False,
    )
    op.create_index("ix_content_risk_rules_risk_level", "content_risk_rules", ["risk_level"], unique=False)
    op.create_index(
        "ix_content_risk_rules_default_action",
        "content_risk_rules",
        ["default_action"],
        unique=False,
    )
    op.create_index("ix_content_risk_rules_enabled", "content_risk_rules", ["enabled"], unique=False)
    op.create_index(
        "ix_content_risk_rules_created_by_user_id",
        "content_risk_rules",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_content_risk_rules_updated_by_user_id",
        "content_risk_rules",
        ["updated_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_content_risk_rules_updated_by_user_id", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_created_by_user_id", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_enabled", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_default_action", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_risk_level", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_risk_category", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_match_mode", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_rule_type", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_name", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_library_id", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_id", table_name="content_risk_rules")
    op.drop_table("content_risk_rules")
