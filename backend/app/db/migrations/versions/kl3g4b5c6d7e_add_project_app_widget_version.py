"""Add project app widget version.

Revision ID: kl3g4b5c6d7e
Revises: jk2f3a4b5c6d
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "kl3g4b5c6d7e"
down_revision: Union[str, Sequence[str], None] = "jk2f3a4b5c6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_apps",
        sa.Column(
            "widget_version",
            sa.String(length=30),
            server_default="1.0.0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("project_apps", "widget_version")
