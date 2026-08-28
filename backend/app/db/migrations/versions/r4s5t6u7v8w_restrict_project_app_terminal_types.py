"""Restrict project application terminal types to API and MCP."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "r4s5t6u7v8w"
down_revision: Union[str, Sequence[str], None] = "pq3r4s5t6u7v"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if "project_apps" not in inspect(conn).get_table_names():
        return

    op.execute(
        sa.text(
            """
            UPDATE project_apps
            SET terminal_type = 'api'
            WHERE terminal_type IS NULL
               OR terminal_type IN ('web', 'h5', 'mini_program', 'admin', 'other')
            """
        )
    )
    op.alter_column(
        "project_apps",
        "terminal_type",
        existing_type=sa.String(length=40),
        server_default="api",
    )


def downgrade() -> None:
    conn = op.get_bind()
    if "project_apps" not in inspect(conn).get_table_names():
        return
    op.alter_column(
        "project_apps",
        "terminal_type",
        existing_type=sa.String(length=40),
        server_default=None,
    )
