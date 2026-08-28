"""Add idempotency key for evaluation case execution.

Revision ID: op2q3r4s5t6u
Revises: no1p2q3r4s5t
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "op2q3r4s5t6u"
down_revision: Union[str, Sequence[str], None] = "no1p2q3r4s5t"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "uq_eval_case_results_run_case_key"


def upgrade() -> None:
    conn = op.get_bind()
    columns = {column["name"] for column in inspect(conn).get_columns("eval_case_results")}
    if "case_key" not in columns:
        op.add_column("eval_case_results", sa.Column("case_key", sa.String(length=100), nullable=True))

    indexes = {index["name"] for index in inspect(conn).get_indexes("eval_case_results")}
    if INDEX_NAME not in indexes:
        op.create_index(
            INDEX_NAME,
            "eval_case_results",
            ["run_id", "case_key"],
            unique=True,
            postgresql_where=sa.text("case_key IS NOT NULL"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    indexes = {index["name"] for index in inspect(conn).get_indexes("eval_case_results")}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name="eval_case_results")
    columns = {column["name"] for column in inspect(conn).get_columns("eval_case_results")}
    if "case_key" in columns:
        op.drop_column("eval_case_results", "case_key")
