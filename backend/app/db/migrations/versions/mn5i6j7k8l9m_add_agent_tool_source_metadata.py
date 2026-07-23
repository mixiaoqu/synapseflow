"""Add source metadata to agent tools.

Revision ID: mn5i6j7k8l9m
Revises: lm4h5c6d7e8f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "mn5i6j7k8l9m"
down_revision: Union[str, Sequence[str], None] = "lm4h5c6d7e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_tools", sa.Column("external_display_name", sa.String(length=100), nullable=True))
    op.add_column("agent_tools", sa.Column("domain", sa.String(length=50), nullable=True))
    op.add_column("agent_tools", sa.Column("action", sa.String(length=20), nullable=True))
    op.add_column("agent_tools", sa.Column("read_only", sa.Boolean(), nullable=True))
    op.add_column("agent_tools", sa.Column("required_permissions", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE agent_tools
        SET external_display_name = COALESCE(NULLIF(name, ''), external_name),
            domain = 'general',
            action = 'execute',
            read_only = false,
            required_permissions = '[]'::json
        """
    )
    for column in ("external_display_name", "domain", "action", "read_only", "required_permissions"):
        op.alter_column("agent_tools", column, nullable=False)
    op.create_index("ix_agent_tools_domain", "agent_tools", ["domain"])
    op.create_index("ix_agent_tools_action", "agent_tools", ["action"])
    op.create_index("ix_agent_tools_read_only", "agent_tools", ["read_only"])


def downgrade() -> None:
    op.drop_index("ix_agent_tools_read_only", table_name="agent_tools")
    op.drop_index("ix_agent_tools_action", table_name="agent_tools")
    op.drop_index("ix_agent_tools_domain", table_name="agent_tools")
    for column in ("required_permissions", "read_only", "action", "domain", "external_display_name"):
        op.drop_column("agent_tools", column)
