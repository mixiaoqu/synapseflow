"""add content risk rule scenes

Revision ID: 4d5e6f7a8b9c
Revises: 3d4e5f6a7b8c
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "4d5e6f7a8b9c"
down_revision = "3d4e5f6a7b8c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "content_risk_rules",
        sa.Column("applies_to_query", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "content_risk_rules",
        sa.Column("applies_to_answer", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_content_risk_rules_applies_to_query",
        "content_risk_rules",
        ["applies_to_query"],
        unique=False,
    )
    op.create_index(
        "ix_content_risk_rules_applies_to_answer",
        "content_risk_rules",
        ["applies_to_answer"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_content_risk_rules_applies_to_answer", table_name="content_risk_rules")
    op.drop_index("ix_content_risk_rules_applies_to_query", table_name="content_risk_rules")
    op.drop_column("content_risk_rules", "applies_to_answer")
    op.drop_column("content_risk_rules", "applies_to_query")
