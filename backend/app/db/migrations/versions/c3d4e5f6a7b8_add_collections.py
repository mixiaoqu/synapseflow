"""add teams, knowledge bases, and document knowledge_base_id

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, name: str) -> bool:
    return name in inspect(conn).get_table_names()


def _documents_has_column(conn, col_name: str) -> bool:
    if "documents" not in inspect(conn).get_table_names():
        return False
    cols = [c["name"] for c in inspect(conn).get_columns("documents")]
    return col_name in cols


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "teams"):
        op.create_table(
            "teams",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("code", sa.String(length=50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_teams_code", "teams", ["code"])

    if not _table_exists(conn, "team_members"):
        op.create_table(
            "team_members",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=30), nullable=False, server_default="member"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
        op.create_index("ix_team_members_user_id", "team_members", ["user_id"])

    if not _table_exists(conn, "knowledge_bases"):
        op.create_table(
            "knowledge_bases",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("team_id", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_knowledge_bases_team_id", "knowledge_bases", ["team_id"])

    if not _table_exists(conn, "knowledge_base_members"):
        op.create_table(
            "knowledge_base_members",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=30), nullable=False, server_default="viewer"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_knowledge_base_members_knowledge_base_id",
            "knowledge_base_members",
            ["knowledge_base_id"],
        )
        op.create_index("ix_knowledge_base_members_user_id", "knowledge_base_members", ["user_id"])

    if not _documents_has_column(conn, "knowledge_base_id"):
        op.add_column("documents", sa.Column("knowledge_base_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_documents_knowledge_base_id",
            "documents",
            "knowledge_bases",
            ["knowledge_base_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_documents_knowledge_base_id", "documents", ["knowledge_base_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if _documents_has_column(conn, "knowledge_base_id"):
        op.drop_index("ix_documents_knowledge_base_id", table_name="documents")
        op.drop_constraint("fk_documents_knowledge_base_id", "documents", type_="foreignkey")
        op.drop_column("documents", "knowledge_base_id")
    if _table_exists(conn, "knowledge_base_members"):
        op.drop_index("ix_knowledge_base_members_user_id", table_name="knowledge_base_members")
        op.drop_index(
            "ix_knowledge_base_members_knowledge_base_id",
            table_name="knowledge_base_members",
        )
        op.drop_table("knowledge_base_members")
    if _table_exists(conn, "knowledge_bases"):
        op.drop_index("ix_knowledge_bases_team_id", table_name="knowledge_bases")
        op.drop_table("knowledge_bases")
    if _table_exists(conn, "team_members"):
        op.drop_index("ix_team_members_user_id", table_name="team_members")
        op.drop_index("ix_team_members_team_id", table_name="team_members")
        op.drop_table("team_members")
    if _table_exists(conn, "teams"):
        op.drop_index("ix_teams_code", table_name="teams")
        op.drop_table("teams")
