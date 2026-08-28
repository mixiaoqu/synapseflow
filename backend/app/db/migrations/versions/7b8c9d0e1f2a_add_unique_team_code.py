"""add unique team code

Revision ID: 7b8c9d0e1f2a
Revises: 001a2b3c4d5e
Create Date: 2026-06-05 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "7b8c9d0e1f2a"
down_revision: Union[str, tuple[str, ...], None] = "001a2b3c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_unique_constraint(conn, table_name: str, constraint_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return constraint_name in {
        item["name"] for item in inspect(conn).get_unique_constraints(table_name)
    }


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "teams") or _has_unique_constraint(conn, "teams", "uq_teams_code"):
        return

    duplicate = conn.execute(
        sa.text(
            """
            SELECT code
            FROM teams
            WHERE code IS NOT NULL AND btrim(code) <> ''
            GROUP BY code
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate:
        raise RuntimeError("teams.code 存在重复值，请先清理重复团队编码后再执行迁移")

    op.create_unique_constraint("uq_teams_code", "teams", ["code"])


def downgrade() -> None:
    conn = op.get_bind()
    if _has_unique_constraint(conn, "teams", "uq_teams_code"):
        op.drop_constraint("uq_teams_code", "teams", type_="unique")
