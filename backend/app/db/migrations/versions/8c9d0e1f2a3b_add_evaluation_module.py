"""add evaluation module

Revision ID: 8c9d0e1f2a3b
Revises: 2b3c4d5e6f7a
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "8c9d0e1f2a3b"
down_revision: Union[str, tuple[str, ...], None] = "2b3c4d5e6f7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def _has_index(conn, table_name: str, index_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return index_name in {item["name"] for item in inspect(conn).get_indexes(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "knowledge_bases") and not _has_column(conn, "knowledge_bases", "purpose"):
        op.add_column(
            "knowledge_bases",
            sa.Column(
                "purpose",
                sa.String(length=30),
                server_default="business",
                nullable=False,
            ),
        )
    if _table_exists(conn, "knowledge_bases") and not _has_index(
        conn,
        "knowledge_bases",
        "ix_knowledge_bases_purpose",
    ):
        op.create_index("ix_knowledge_bases_purpose", "knowledge_bases", ["purpose"])

    if not _table_exists(conn, "eval_datasets"):
        op.create_table(
            "eval_datasets",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.String(length=50), server_default="v1", nullable=False),
            sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_eval_datasets_id", "eval_datasets", ["id"])
        op.create_index("ix_eval_datasets_name", "eval_datasets", ["name"])
        op.create_index("ix_eval_datasets_knowledge_base_id", "eval_datasets", ["knowledge_base_id"])
        op.create_index("ix_eval_datasets_status", "eval_datasets", ["status"])
        op.create_index("ix_eval_datasets_created_by", "eval_datasets", ["created_by"])

    if not _table_exists(conn, "eval_cases"):
        op.create_table(
            "eval_cases",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("dataset_id", sa.Integer(), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("expected_answer", sa.Text(), nullable=False),
            sa.Column("expected_doc_ids", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("expected_snippets", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("expected_chunk_ids", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["dataset_id"], ["eval_datasets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_eval_cases_id", "eval_cases", ["id"])
        op.create_index("ix_eval_cases_dataset_id", "eval_cases", ["dataset_id"])
        op.create_index("ix_eval_cases_enabled", "eval_cases", ["enabled"])

    if not _table_exists(conn, "eval_runs"):
        op.create_table(
            "eval_runs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("dataset_id", sa.Integer(), nullable=False),
            sa.Column("run_name", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
            sa.Column("model_config", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("kb_snapshot", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("total_cases", sa.Integer(), server_default="0", nullable=False),
            sa.Column("passed_cases", sa.Integer(), server_default="0", nullable=False),
            sa.Column("failed_cases", sa.Integer(), server_default="0", nullable=False),
            sa.Column("average_score", sa.Integer(), server_default="0", nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["dataset_id"], ["eval_datasets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_eval_runs_id", "eval_runs", ["id"])
        op.create_index("ix_eval_runs_dataset_id", "eval_runs", ["dataset_id"])
        op.create_index("ix_eval_runs_status", "eval_runs", ["status"])
        op.create_index("ix_eval_runs_created_by", "eval_runs", ["created_by"])

    if not _table_exists(conn, "eval_case_results"):
        op.create_table(
            "eval_case_results",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="failed", nullable=False),
            sa.Column("score", sa.Integer(), server_default="0", nullable=False),
            sa.Column("actual_answer", sa.Text(), server_default="", nullable=False),
            sa.Column("retrieved_doc_ids", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("retrieved_chunk_ids", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("judge_result", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["case_id"], ["eval_cases.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["run_id"], ["eval_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_eval_case_results_id", "eval_case_results", ["id"])
        op.create_index("ix_eval_case_results_run_id", "eval_case_results", ["run_id"])
        op.create_index("ix_eval_case_results_case_id", "eval_case_results", ["case_id"])
        op.create_index("ix_eval_case_results_status", "eval_case_results", ["status"])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "eval_case_results"):
        op.drop_index("ix_eval_case_results_status", table_name="eval_case_results")
        op.drop_index("ix_eval_case_results_case_id", table_name="eval_case_results")
        op.drop_index("ix_eval_case_results_run_id", table_name="eval_case_results")
        op.drop_index("ix_eval_case_results_id", table_name="eval_case_results")
        op.drop_table("eval_case_results")
    if _table_exists(conn, "eval_runs"):
        op.drop_index("ix_eval_runs_created_by", table_name="eval_runs")
        op.drop_index("ix_eval_runs_status", table_name="eval_runs")
        op.drop_index("ix_eval_runs_dataset_id", table_name="eval_runs")
        op.drop_index("ix_eval_runs_id", table_name="eval_runs")
        op.drop_table("eval_runs")
    if _table_exists(conn, "eval_cases"):
        op.drop_index("ix_eval_cases_enabled", table_name="eval_cases")
        op.drop_index("ix_eval_cases_dataset_id", table_name="eval_cases")
        op.drop_index("ix_eval_cases_id", table_name="eval_cases")
        op.drop_table("eval_cases")
    if _table_exists(conn, "eval_datasets"):
        op.drop_index("ix_eval_datasets_created_by", table_name="eval_datasets")
        op.drop_index("ix_eval_datasets_status", table_name="eval_datasets")
        op.drop_index("ix_eval_datasets_knowledge_base_id", table_name="eval_datasets")
        op.drop_index("ix_eval_datasets_name", table_name="eval_datasets")
        op.drop_index("ix_eval_datasets_id", table_name="eval_datasets")
        op.drop_table("eval_datasets")
    if _table_exists(conn, "knowledge_bases"):
        if _has_index(conn, "knowledge_bases", "ix_knowledge_bases_purpose"):
            op.drop_index("ix_knowledge_bases_purpose", table_name="knowledge_bases")
        if _has_column(conn, "knowledge_bases", "purpose"):
            op.drop_column("knowledge_bases", "purpose")
