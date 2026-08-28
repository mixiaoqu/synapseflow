"""Add encrypted credentials for MCP servers.

Revision ID: hi0d1e2f3a4b
Revises: gh9c0d1e2f3a
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "hi0d1e2f3a4b"
down_revision: Union[str, Sequence[str], None] = "gh9c0d1e2f3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mcp_servers", sa.Column("auth_token_encrypted", sa.Text(), nullable=True))
    op.add_column(
        "mcp_servers",
        sa.Column("auth_token_last_four", sa.String(length=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_servers", "auth_token_last_four")
    op.drop_column("mcp_servers", "auth_token_encrypted")
