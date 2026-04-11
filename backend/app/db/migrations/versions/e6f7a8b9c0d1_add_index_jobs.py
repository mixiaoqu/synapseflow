"""add index jobs

Revision ID: e6f7a8b9c0d1
Revises: f4d5e6f7a8b9
Create Date: 2026-04-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "f4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, name: str) -> bool:
    return name in inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "index_jobs"):
        op.create_table(
            "index_jobs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("knowledge_base_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("job_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
            sa.Column("total_documents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("queued_documents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("processing_documents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("indexed_documents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_documents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_index_jobs_user_id", "index_jobs", ["user_id"])
        op.create_index("ix_index_jobs_knowledge_base_id", "index_jobs", ["knowledge_base_id"])
        op.create_index("ix_index_jobs_job_type", "index_jobs", ["job_type"])
        op.create_index("ix_index_jobs_status", "index_jobs", ["status"])

    if not _table_exists(conn, "index_job_documents"):
        op.create_table(
            "index_job_documents",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("expected_content_hash", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("indexed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["job_id"], ["index_jobs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("job_id", "document_id", name="uq_index_job_documents_job_document"),
        )
        op.create_index("ix_index_job_documents_job_id", "index_job_documents", ["job_id"])
        op.create_index("ix_index_job_documents_document_id", "index_job_documents", ["document_id"])
        op.create_index("ix_index_job_documents_status", "index_job_documents", ["status"])


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "index_job_documents"):
        op.drop_index("ix_index_job_documents_status", table_name="index_job_documents")
        op.drop_index("ix_index_job_documents_document_id", table_name="index_job_documents")
        op.drop_index("ix_index_job_documents_job_id", table_name="index_job_documents")
        op.drop_table("index_job_documents")

    if _table_exists(conn, "index_jobs"):
        op.drop_index("ix_index_jobs_status", table_name="index_jobs")
        op.drop_index("ix_index_jobs_job_type", table_name="index_jobs")
        op.drop_index("ix_index_jobs_knowledge_base_id", table_name="index_jobs")
        op.drop_index("ix_index_jobs_user_id", table_name="index_jobs")
        op.drop_table("index_jobs")
