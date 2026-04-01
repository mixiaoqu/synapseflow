"""add users and auth foundation

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext
from sqlalchemy import inspect

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _foreign_key_names(conn) -> set[str]:
    names: set[str] = set()
    inspector = inspect(conn)
    for table_name in (
        "documents",
        "knowledge_bases",
        "team_members",
        "knowledge_base_members",
    ):
        if table_name not in inspector.get_table_names():
            continue
        for fk in inspector.get_foreign_keys(table_name):
            if fk.get("name"):
                names.add(fk["name"])
    return names


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if "users" not in inspector.get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=100), nullable=True),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        )
        op.create_index("ix_users_username", "users", ["username"], unique=True)
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    legacy_password_hash = pwd_context.hash("ChangeMe123!")
    conn.execute(
        sa.text(
            """
            INSERT INTO users (id, username, email, full_name, hashed_password, is_active, created_at, updated_at)
            SELECT 1, 'admin', 'admin@synapseflow.local', 'Bootstrap Admin', :hashed_password, true, now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = 1)
            """
        ),
        {"hashed_password": legacy_password_hash},
    )

    conn.execute(sa.text("ALTER SEQUENCE users_id_seq RESTART WITH 2"))

    fk_names = _foreign_key_names(conn)

    if "documents" in inspector.get_table_names():
        op.alter_column("documents", "user_id", server_default=None)
        if "fk_documents_user_id_users" not in fk_names:
            op.create_foreign_key(
                "fk_documents_user_id_users",
                "documents",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    if "knowledge_bases" in inspector.get_table_names():
        op.alter_column("knowledge_bases", "user_id", server_default=None)
        if "fk_knowledge_bases_user_id_users" not in fk_names:
            op.create_foreign_key(
                "fk_knowledge_bases_user_id_users",
                "knowledge_bases",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    if "team_members" in inspector.get_table_names():
        if "fk_team_members_user_id_users" not in fk_names:
            op.create_foreign_key(
                "fk_team_members_user_id_users",
                "team_members",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    if "knowledge_base_members" in inspector.get_table_names():
        if "fk_knowledge_base_members_user_id_users" not in fk_names:
            op.create_foreign_key(
                "fk_knowledge_base_members_user_id_users",
                "knowledge_base_members",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    if "teams" in inspector.get_table_names() and "team_members" in inspector.get_table_names():
        conn.execute(
            sa.text(
                """
                INSERT INTO team_members (team_id, user_id, role, created_at, updated_at)
                SELECT t.id, 1, 'owner', now(), now()
                FROM teams t
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM team_members tm
                    WHERE tm.team_id = t.id AND tm.user_id = 1
                )
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    fk_names = _foreign_key_names(conn)

    if "fk_knowledge_base_members_user_id_users" in fk_names:
        op.drop_constraint(
            "fk_knowledge_base_members_user_id_users",
            "knowledge_base_members",
            type_="foreignkey",
        )
    if "fk_team_members_user_id_users" in fk_names:
        op.drop_constraint("fk_team_members_user_id_users", "team_members", type_="foreignkey")
    if "fk_knowledge_bases_user_id_users" in fk_names:
        op.drop_constraint(
            "fk_knowledge_bases_user_id_users",
            "knowledge_bases",
            type_="foreignkey",
        )
    if "fk_documents_user_id_users" in fk_names:
        op.drop_constraint("fk_documents_user_id_users", "documents", type_="foreignkey")

    inspector = inspect(conn)
    if "users" in inspector.get_table_names():
        op.drop_index("ix_users_email", table_name="users")
        op.drop_index("ix_users_username", table_name="users")
        op.drop_table("users")
