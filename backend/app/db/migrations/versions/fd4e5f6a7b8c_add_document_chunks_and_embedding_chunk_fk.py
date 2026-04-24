"""add document chunks and embedding chunk foreign key

Revision ID: fd4e5f6a7b8c
Revises: fc3d4e5f6a7b
Create Date: 2026-04-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "fd4e5f6a7b8c"
down_revision: Union[str, None] = "fc3d4e5f6a7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, name: str) -> bool:
    return name in inspect(conn).get_table_names()


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return index_name in {item["name"] for item in inspect(conn).get_indexes(table_name)}


def _foreign_key_exists(conn, table_name: str, fk_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return fk_name in {item["name"] for item in inspect(conn).get_foreign_keys(table_name)}


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "document_chunks"):
        op.create_table(
            "document_chunks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("chunk_kind", sa.String(length=20), nullable=False),
            sa.Column("parent_chunk_id", sa.Integer(), nullable=True),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("prev_chunk_id", sa.Integer(), nullable=True),
            sa.Column("next_chunk_id", sa.Integer(), nullable=True),
            sa.Column("section_path", sa.String(length=1024), nullable=True),
            sa.Column("block_types", sa.JSON(), nullable=True),
            sa.Column("start_offset", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("end_offset", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("search_text", sa.Text(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["prev_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["next_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "document_id",
                "chunk_kind",
                "chunk_index",
                name="uq_document_chunks_doc_kind_index",
            ),
        )

    for index_name, columns in (
        ("ix_document_chunks_document_id", ["document_id"]),
        ("ix_document_chunks_chunk_kind", ["chunk_kind"]),
        ("ix_document_chunks_parent_chunk_id", ["parent_chunk_id"]),
        ("ix_document_chunks_prev_chunk_id", ["prev_chunk_id"]),
        ("ix_document_chunks_next_chunk_id", ["next_chunk_id"]),
    ):
        if not _index_exists(conn, "document_chunks", index_name):
            op.create_index(index_name, "document_chunks", columns, unique=False)

    if not _column_exists(conn, "embeddings", "document_chunk_id"):
        op.add_column("embeddings", sa.Column("document_chunk_id", sa.Integer(), nullable=True))

    if not _foreign_key_exists(conn, "embeddings", "fk_embeddings_document_chunk_id"):
        op.create_foreign_key(
            "fk_embeddings_document_chunk_id",
            "embeddings",
            "document_chunks",
            ["document_chunk_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if not _index_exists(conn, "embeddings", "ix_embeddings_document_chunk_id"):
        op.create_index("ix_embeddings_document_chunk_id", "embeddings", ["document_chunk_id"], unique=False)

    # This rollout explicitly drops compatibility with pre-DocumentChunk embeddings.
    op.execute("DELETE FROM embeddings WHERE document_chunk_id IS NULL")
    op.execute(
        """
        UPDATE documents AS d
        SET index_status = 'failed',
            index_error = 'Legacy embeddings were removed during the DocumentChunk rollout. Delete and re-upload this document.',
            indexed_at = NULL
        WHERE d.index_status = 'indexed'
          AND NOT EXISTS (
              SELECT 1
              FROM embeddings AS e
              WHERE e.document_id = d.id
          )
        """
    )
    op.alter_column("embeddings", "document_chunk_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    conn = op.get_bind()

    if _column_exists(conn, "embeddings", "document_chunk_id"):
        op.alter_column("embeddings", "document_chunk_id", existing_type=sa.Integer(), nullable=True)
    if _index_exists(conn, "embeddings", "ix_embeddings_document_chunk_id"):
        op.drop_index("ix_embeddings_document_chunk_id", table_name="embeddings")
    if _foreign_key_exists(conn, "embeddings", "fk_embeddings_document_chunk_id"):
        op.drop_constraint("fk_embeddings_document_chunk_id", "embeddings", type_="foreignkey")
    if _column_exists(conn, "embeddings", "document_chunk_id"):
        op.drop_column("embeddings", "document_chunk_id")

    if _table_exists(conn, "document_chunks"):
        for index_name in (
            "ix_document_chunks_next_chunk_id",
            "ix_document_chunks_prev_chunk_id",
            "ix_document_chunks_parent_chunk_id",
            "ix_document_chunks_chunk_kind",
            "ix_document_chunks_document_id",
        ):
            if _index_exists(conn, "document_chunks", index_name):
                op.drop_index(index_name, table_name="document_chunks")
        op.drop_table("document_chunks")
