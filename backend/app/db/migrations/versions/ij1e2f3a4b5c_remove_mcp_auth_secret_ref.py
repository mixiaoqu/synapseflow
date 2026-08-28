"""Remove the deprecated MCP secret reference field.

Revision ID: ij1e2f3a4b5c
Revises: hi0d1e2f3a4b
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ij1e2f3a4b5c"
down_revision: Union[str, Sequence[str], None] = "hi0d1e2f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("mcp_servers", "auth_secret_ref")


def downgrade() -> None:
    op.add_column(
        "mcp_servers",
        sa.Column("auth_secret_ref", sa.String(length=255), nullable=True),
    )
