"""add sensitive word management

Revision ID: e1f2a3b4c5d6
Revises: d5e6f7a8b9c0
Create Date: 2026-04-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "sensitive_word_settings"):
        op.create_table(
            "sensitive_word_settings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("block_query", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "block_document_publish",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_sensitive_word_settings_team_id",
            "sensitive_word_settings",
            ["team_id"],
            unique=False,
        )
        op.create_index(
            "ix_sensitive_word_settings_created_by_user_id",
            "sensitive_word_settings",
            ["created_by_user_id"],
            unique=False,
        )
        op.create_index(
            "ix_sensitive_word_settings_updated_by_user_id",
            "sensitive_word_settings",
            ["updated_by_user_id"],
            unique=False,
        )

    if not _table_exists(conn, "sensitive_words"):
        op.create_table(
            "sensitive_words",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=True),
            sa.Column("word", sa.String(length=255), nullable=False),
            sa.Column("normalized_word", sa.String(length=255), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=True),
            sa.Column("match_mode", sa.String(length=20), nullable=False, server_default="contains"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "team_id",
                "normalized_word",
                name="uq_sensitive_words_team_normalized",
            ),
        )
        op.create_index("ix_sensitive_words_team_id", "sensitive_words", ["team_id"], unique=False)
        op.create_index(
            "ix_sensitive_words_normalized_word",
            "sensitive_words",
            ["normalized_word"],
            unique=False,
        )
        op.create_index("ix_sensitive_words_category", "sensitive_words", ["category"], unique=False)
        op.create_index("ix_sensitive_words_created_by_user_id", "sensitive_words", ["created_by_user_id"], unique=False)
        op.create_index("ix_sensitive_words_updated_by_user_id", "sensitive_words", ["updated_by_user_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "sensitive_words"):
        op.drop_index("ix_sensitive_words_updated_by_user_id", table_name="sensitive_words")
        op.drop_index("ix_sensitive_words_created_by_user_id", table_name="sensitive_words")
        op.drop_index("ix_sensitive_words_category", table_name="sensitive_words")
        op.drop_index("ix_sensitive_words_normalized_word", table_name="sensitive_words")
        op.drop_index("ix_sensitive_words_team_id", table_name="sensitive_words")
        op.drop_table("sensitive_words")

    if _table_exists(conn, "sensitive_word_settings"):
        op.drop_index(
            "ix_sensitive_word_settings_updated_by_user_id",
            table_name="sensitive_word_settings",
        )
        op.drop_index(
            "ix_sensitive_word_settings_created_by_user_id",
            table_name="sensitive_word_settings",
        )
        op.drop_index("ix_sensitive_word_settings_team_id", table_name="sensitive_word_settings")
        op.drop_table("sensitive_word_settings")
