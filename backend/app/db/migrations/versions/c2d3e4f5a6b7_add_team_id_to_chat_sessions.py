"""add team_id to chat sessions

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {item["name"] for item in inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "chat_sessions") and not _has_column(conn, "chat_sessions", "team_id"):
        op.add_column("chat_sessions", sa.Column("team_id", sa.Integer(), nullable=True))
        op.create_index("ix_chat_sessions_team_id", "chat_sessions", ["team_id"], unique=False)
        op.create_foreign_key(
            "fk_chat_sessions_team_id_teams",
            "chat_sessions",
            "teams",
            ["team_id"],
            ["id"],
            ondelete="SET NULL",
        )
        conn.execute(
            sa.text(
                """
                UPDATE chat_sessions cs
                SET team_id = kb.team_id
                FROM knowledge_bases kb
                WHERE cs.knowledge_base_id = kb.id
                  AND cs.team_id IS NULL
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "chat_sessions") and _has_column(conn, "chat_sessions", "team_id"):
        fk_names = {
            item.get("name")
            for item in inspect(conn).get_foreign_keys("chat_sessions")
            if item.get("name")
        }
        if "fk_chat_sessions_team_id_teams" in fk_names:
            op.drop_constraint("fk_chat_sessions_team_id_teams", "chat_sessions", type_="foreignkey")
        op.drop_index("ix_chat_sessions_team_id", table_name="chat_sessions")
        op.drop_column("chat_sessions", "team_id")
