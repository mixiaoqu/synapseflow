"""add products and align project/embed schema

Revision ID: fe6a7b8c9d0e
Revises: fd4e5f6a7b8c
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "fe6a7b8c9d0e"
down_revision: Union[str, None] = "fd4e5f6a7b8c"
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


def _unique_constraint_exists(conn, table_name: str, constraint_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return constraint_name in {
        item["name"] for item in inspect(conn).get_unique_constraints(table_name) if item.get("name")
    }


def _drop_projects_code_uniqueness(conn) -> None:
    inspector = inspect(conn)
    for item in inspector.get_unique_constraints("projects"):
        columns = item.get("column_names") or []
        name = item.get("name")
        if columns == ["code"] and name:
            op.drop_constraint(name, "projects", type_="unique")
    for item in inspector.get_indexes("projects"):
        columns = item.get("column_names") or []
        name = item.get("name")
        if item.get("unique") and columns == ["code"] and name:
            op.drop_index(name, table_name="projects")


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "products"):
        op.create_table(
            "products",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_products_code"),
        )

    for index_name, columns in (
        ("ix_products_id", ["id"]),
        ("ix_products_team_id", ["team_id"]),
        ("ix_products_code", ["code"]),
        ("ix_products_is_active", ["is_active"]),
    ):
        if not _index_exists(conn, "products", index_name):
            op.create_index(index_name, "products", columns, unique=False)

    if _table_exists(conn, "projects"):
        if not _column_exists(conn, "projects", "product_id"):
            op.add_column("projects", sa.Column("product_id", sa.Integer(), nullable=True))
        if not _index_exists(conn, "projects", "ix_projects_product_id"):
            op.create_index("ix_projects_product_id", "projects", ["product_id"], unique=False)
        if not _foreign_key_exists(conn, "projects", "fk_projects_product_id_products"):
            op.create_foreign_key(
                "fk_projects_product_id_products",
                "projects",
                "products",
                ["product_id"],
                ["id"],
                ondelete="CASCADE",
            )
        _drop_projects_code_uniqueness(conn)
        if not _unique_constraint_exists(conn, "projects", "uq_projects_product_code"):
            op.create_unique_constraint("uq_projects_product_code", "projects", ["product_id", "code"])

    for table_name in ("chat_sessions", "kb_chat_logs"):
        if _table_exists(conn, table_name):
            if not _column_exists(conn, table_name, "product_id"):
                op.add_column(table_name, sa.Column("product_id", sa.Integer(), nullable=True))
            index_name = f"ix_{table_name}_product_id"
            if not _index_exists(conn, table_name, index_name):
                op.create_index(index_name, table_name, ["product_id"], unique=False)
            fk_name = f"fk_{table_name}_product_id_products"
            if not _foreign_key_exists(conn, table_name, fk_name):
                op.create_foreign_key(
                    fk_name,
                    table_name,
                    "products",
                    ["product_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if _column_exists(conn, table_name, "source"):
                op.drop_column(table_name, "source")


def downgrade() -> None:
    conn = op.get_bind()

    for table_name in ("kb_chat_logs", "chat_sessions"):
        if _table_exists(conn, table_name):
            if _column_exists(conn, table_name, "product_id"):
                fk_name = f"fk_{table_name}_product_id_products"
                if _foreign_key_exists(conn, table_name, fk_name):
                    op.drop_constraint(fk_name, table_name, type_="foreignkey")
                index_name = f"ix_{table_name}_product_id"
                if _index_exists(conn, table_name, index_name):
                    op.drop_index(index_name, table_name=table_name)
                op.drop_column(table_name, "product_id")
            if not _column_exists(conn, table_name, "source"):
                op.add_column(table_name, sa.Column("source", sa.String(length=80), nullable=True))

    if _table_exists(conn, "projects"):
        if _unique_constraint_exists(conn, "projects", "uq_projects_product_code"):
            op.drop_constraint("uq_projects_product_code", "projects", type_="unique")
        if _foreign_key_exists(conn, "projects", "fk_projects_product_id_products"):
            op.drop_constraint("fk_projects_product_id_products", "projects", type_="foreignkey")
        if _index_exists(conn, "projects", "ix_projects_product_id"):
            op.drop_index("ix_projects_product_id", table_name="projects")
        if _column_exists(conn, "projects", "product_id"):
            op.drop_column("projects", "product_id")

    if _table_exists(conn, "products"):
        for index_name in ("ix_products_is_active", "ix_products_code", "ix_products_team_id", "ix_products_id"):
            if _index_exists(conn, "products", index_name):
                op.drop_index(index_name, table_name="products")
        op.drop_table("products")
