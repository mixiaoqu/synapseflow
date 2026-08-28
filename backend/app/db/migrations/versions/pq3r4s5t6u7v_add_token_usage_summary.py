"""Add token usage summaries to chat and evaluation records.

Revision ID: pq3r4s5t6u7v
Revises: op2q3r4s5t6u
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "pq3r4s5t6u7v"
down_revision: Union[str, Sequence[str], None] = "op2q3r4s5t6u"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _token_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=True),
    )


def upgrade() -> None:
    for table_name in ("kb_chat_logs", "eval_runs", "eval_case_results"):
        for column in _token_columns():
            op.add_column(table_name, column)


def downgrade() -> None:
    for table_name in ("eval_case_results", "eval_runs", "kb_chat_logs"):
        for column_name in ("token_usage", "estimated_cost", "total_tokens", "output_tokens", "input_tokens"):
            op.drop_column(table_name, column_name)
