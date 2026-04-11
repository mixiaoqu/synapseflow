"""make datetimes timezone aware

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-04-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": ("created_at", "updated_at"),
    "teams": ("created_at", "updated_at"),
    "team_members": ("created_at", "updated_at"),
    "knowledge_bases": ("created_at", "updated_at"),
    "knowledge_base_members": ("created_at", "updated_at"),
    "document_categories": ("created_at", "updated_at"),
    "documents": ("indexed_at", "created_at", "updated_at"),
    "index_jobs": ("started_at", "finished_at", "created_at", "updated_at"),
    "index_job_documents": ("indexed_at", "created_at", "updated_at"),
    "chat_sessions": ("created_at", "updated_at"),
    "chat_messages": ("created_at",),
}


def _table_exists(conn, name: str) -> bool:
    return name in inspect(conn).get_table_names()


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name
        for column in inspect(conn).get_columns(table_name)
    )


def _alter_columns(*, upgrade: bool) -> None:
    conn = op.get_bind()
    target_type = sa.DateTime(timezone=True) if upgrade else sa.DateTime(timezone=False)

    for table_name, column_names in TABLE_COLUMNS.items():
        if not _table_exists(conn, table_name):
            continue
        for column_name in column_names:
            if not _column_exists(conn, table_name, column_name):
                continue
            using_expr = (
                f"{column_name} AT TIME ZONE 'UTC'"
                if upgrade
                else f"{column_name} AT TIME ZONE 'UTC'"
            )
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(),
                type_=target_type,
                postgresql_using=using_expr,
                existing_nullable=True,
            )


def upgrade() -> None:
    _alter_columns(upgrade=True)


def downgrade() -> None:
    _alter_columns(upgrade=False)
