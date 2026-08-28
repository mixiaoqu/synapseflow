"""Add project app access credentials.

Revision ID: jk2f3a4b5c6d
Revises: ij1e2f3a4b5c
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "jk2f3a4b5c6d"
down_revision: Union[str, Sequence[str], None] = "ij1e2f3a4b5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_app_access_credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_app_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=80), nullable=False),
        sa.Column("client_secret_digest", sa.String(length=64), nullable=False),
        sa.Column("client_secret_last_four", sa.String(length=4), nullable=False),
        sa.Column("allowed_origins", sa.JSON(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
        sa.UniqueConstraint("project_app_id"),
    )
    op.create_index(
        op.f("ix_project_app_access_credentials_enabled"),
        "project_app_access_credentials",
        ["enabled"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("project_app_access_credentials")
