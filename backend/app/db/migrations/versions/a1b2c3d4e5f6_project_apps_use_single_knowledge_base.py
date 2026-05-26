"""project apps use single knowledge base

Revision ID: ab1c2d3e4f5a
Revises: 2c3d4e5f6a7b, ff7a8b9c0d1e
Create Date: 2026-05-26 12:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ab1c2d3e4f5a"
down_revision = ("2c3d4e5f6a7b", "ff7a8b9c0d1e")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_apps", sa.Column("knowledge_base_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_project_apps_knowledge_base_id",
        "project_apps",
        "knowledge_bases",
        ["knowledge_base_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_project_apps_knowledge_base_id",
        "project_apps",
        ["knowledge_base_id"],
        unique=False,
    )
    op.execute(
        """
        UPDATE project_apps AS pa
        SET knowledge_base_id = pakb.knowledge_base_id
        FROM (
            SELECT project_app_id, MIN(knowledge_base_id) AS knowledge_base_id
            FROM project_app_knowledge_bases
            GROUP BY project_app_id
        ) AS pakb
        WHERE pa.id = pakb.project_app_id
        """
    )
    op.drop_index("ix_project_app_knowledge_bases_knowledge_base_id", table_name="project_app_knowledge_bases")
    op.drop_index("ix_project_app_knowledge_bases_project_app_id", table_name="project_app_knowledge_bases")
    op.drop_index("ix_project_app_knowledge_bases_id", table_name="project_app_knowledge_bases")
    op.drop_table("project_app_knowledge_bases")


def downgrade() -> None:
    op.create_table(
        "project_app_knowledge_bases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_app_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_app_id", "knowledge_base_id", name="uq_project_app_kbs_app_kb"),
    )
    op.create_index(
        "ix_project_app_knowledge_bases_id",
        "project_app_knowledge_bases",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_project_app_knowledge_bases_project_app_id",
        "project_app_knowledge_bases",
        ["project_app_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_app_knowledge_bases_knowledge_base_id",
        "project_app_knowledge_bases",
        ["knowledge_base_id"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO project_app_knowledge_bases (project_app_id, knowledge_base_id, created_at)
        SELECT id, knowledge_base_id, created_at
        FROM project_apps
        WHERE knowledge_base_id IS NOT NULL
        """
    )
    op.drop_index("ix_project_apps_knowledge_base_id", table_name="project_apps")
    op.drop_constraint("fk_project_apps_knowledge_base_id", "project_apps", type_="foreignkey")
    op.drop_column("project_apps", "knowledge_base_id")
