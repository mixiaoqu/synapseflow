"""add knowledge_base is_active

Revision ID: 4b5c6d7e8f9a
Revises: 252a9a952580
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa


revision = "4b5c6d7e8f9a"
down_revision = "252a9a952580"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_bases",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index("ix_knowledge_bases_is_active", "knowledge_bases", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_bases_is_active", table_name="knowledge_bases")
    op.drop_column("knowledge_bases", "is_active")
