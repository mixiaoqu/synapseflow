"""Release identities for soft-deleted users.

Revision ID: 1a2b3c4d5e6f
Revises: 0f1e2d3c4b5a
Create Date: 2026-06-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "1a2b3c4d5e6f"
down_revision = "0f1e2d3c4b5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET
                username = 'deleted_user_' || id,
                email = 'deleted_user_' || id || '@deleted.local'
            WHERE deleted_at IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    pass
