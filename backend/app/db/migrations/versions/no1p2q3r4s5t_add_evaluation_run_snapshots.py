"""Add immutable snapshots to evaluation runs.

Revision ID: no1p2q3r4s5t
Revises: mn5i6j7k8l9m
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "no1p2q3r4s5t"
down_revision: Union[str, Sequence[str], None] = "mn5i6j7k8l9m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def _has_index(conn, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspect(conn).get_indexes(table_name)}


def _case_foreign_key_name(conn) -> str | None:
    for foreign_key in inspect(conn).get_foreign_keys("eval_case_results"):
        if foreign_key["constrained_columns"] == ["case_id"]:
            return foreign_key["name"]
    return None


def upgrade() -> None:
    conn = op.get_bind()

    for column_name in ("assistant_snapshot", "case_snapshot", "policy_snapshot"):
        if not _has_column(conn, "eval_runs", column_name):
            op.add_column(
                "eval_runs",
                sa.Column(column_name, sa.JSON(), server_default="{}", nullable=False),
            )

    if not _has_column(conn, "eval_runs", "heartbeat_at"):
        op.add_column("eval_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_index(conn, "eval_runs", "ix_eval_runs_heartbeat_at"):
        op.create_index("ix_eval_runs_heartbeat_at", "eval_runs", ["heartbeat_at"])
    if not _has_column(conn, "eval_runs", "error_message"):
        op.add_column("eval_runs", sa.Column("error_message", sa.Text(), nullable=True))

    if not _has_column(conn, "eval_case_results", "case_snapshot"):
        op.add_column(
            "eval_case_results",
            sa.Column("case_snapshot", sa.JSON(), server_default="{}", nullable=False),
        )

    foreign_key_name = _case_foreign_key_name(conn)
    if foreign_key_name:
        op.drop_constraint(foreign_key_name, "eval_case_results", type_="foreignkey")
    op.alter_column("eval_case_results", "case_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "fk_eval_case_results_case_id",
        "eval_case_results",
        "eval_cases",
        ["case_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_eval_case_results_case_id", "eval_case_results", type_="foreignkey")
    op.alter_column("eval_case_results", "case_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "eval_case_results_case_id_fkey",
        "eval_case_results",
        "eval_cases",
        ["case_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("eval_case_results", "case_snapshot")
    op.drop_column("eval_runs", "error_message")
    op.drop_index("ix_eval_runs_heartbeat_at", table_name="eval_runs")
    op.drop_column("eval_runs", "heartbeat_at")
    for column_name in ("policy_snapshot", "case_snapshot", "assistant_snapshot"):
        op.drop_column("eval_runs", column_name)
