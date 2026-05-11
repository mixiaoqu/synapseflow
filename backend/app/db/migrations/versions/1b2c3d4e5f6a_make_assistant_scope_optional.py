"""make assistant knowledge base scope optional

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "1b2c3d4e5f6a"
down_revision = "0a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("assistant_profiles", "knowledge_base_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("assistant_profiles", "knowledge_base_id", existing_type=sa.Integer(), nullable=False)
