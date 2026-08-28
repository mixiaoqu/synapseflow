"""remove knowledge base branching

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa


revision = "2c3d4e5f6a7b"
down_revision = "1b2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_app_knowledge_bases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_app_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
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
        sa.text(
            """
            INSERT INTO project_app_knowledge_bases (project_app_id, knowledge_base_id, created_at)
            SELECT DISTINCT project_app_id, knowledge_base_id, created_at
            FROM project_app_knowledge_base_branches
            """
        )
    )

    op.drop_constraint("fk_documents_knowledge_base_branch_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_knowledge_base_branch_id", table_name="documents")
    op.drop_column("documents", "knowledge_base_branch_id")

    op.drop_column("chat_sessions", "knowledge_base_branch_ids")
    op.drop_column("kb_chat_logs", "knowledge_base_branch_ids")

    op.drop_index(
        "ix_project_app_knowledge_base_branches_branch_id",
        table_name="project_app_knowledge_base_branches",
    )
    op.drop_index(
        "ix_project_app_knowledge_base_branches_knowledge_base_id",
        table_name="project_app_knowledge_base_branches",
    )
    op.drop_index(
        "ix_project_app_knowledge_base_branches_project_app_id",
        table_name="project_app_knowledge_base_branches",
    )
    op.drop_index(
        "ix_project_app_knowledge_base_branches_id",
        table_name="project_app_knowledge_base_branches",
    )
    op.drop_table("project_app_knowledge_base_branches")

    op.drop_index("ix_knowledge_base_branches_created_by_user_id", table_name="knowledge_base_branches")
    op.drop_index("ix_knowledge_base_branches_is_active", table_name="knowledge_base_branches")
    op.drop_index("ix_knowledge_base_branches_code", table_name="knowledge_base_branches")
    op.drop_index("ix_knowledge_base_branches_knowledge_base_id", table_name="knowledge_base_branches")
    op.drop_index("ix_knowledge_base_branches_id", table_name="knowledge_base_branches")
    op.drop_table("knowledge_base_branches")


def downgrade() -> None:
    op.create_table(
        "knowledge_base_branches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("knowledge_base_id", "code", name="uq_knowledge_base_branches_kb_code"),
    )
    op.create_index("ix_knowledge_base_branches_id", "knowledge_base_branches", ["id"], unique=False)
    op.create_index(
        "ix_knowledge_base_branches_knowledge_base_id",
        "knowledge_base_branches",
        ["knowledge_base_id"],
        unique=False,
    )
    op.create_index("ix_knowledge_base_branches_code", "knowledge_base_branches", ["code"], unique=False)
    op.create_index(
        "ix_knowledge_base_branches_is_active",
        "knowledge_base_branches",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_base_branches_created_by_user_id",
        "knowledge_base_branches",
        ["created_by_user_id"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO knowledge_base_branches (
                knowledge_base_id, code, name, description, is_active, created_by_user_id, created_at, updated_at
            )
            SELECT kb.id, 'default', '默认版本', NULL, true, kb.user_id, kb.created_at, kb.updated_at
            FROM knowledge_bases kb
            """
        )
    )

    op.add_column("documents", sa.Column("knowledge_base_branch_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE documents AS d
            SET knowledge_base_branch_id = kbb.id
            FROM knowledge_base_branches AS kbb
            WHERE d.knowledge_base_id = kbb.knowledge_base_id
              AND kbb.code = 'default'
            """
        )
    )
    op.alter_column("documents", "knowledge_base_branch_id", nullable=False)
    op.create_index("ix_documents_knowledge_base_branch_id", "documents", ["knowledge_base_branch_id"], unique=False)
    op.create_foreign_key(
        "fk_documents_knowledge_base_branch_id",
        "documents",
        "knowledge_base_branches",
        ["knowledge_base_branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "chat_sessions",
        sa.Column("knowledge_base_branch_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "kb_chat_logs",
        sa.Column("knowledge_base_branch_ids", sa.JSON(), nullable=False, server_default="[]"),
    )

    op.create_table(
        "project_app_knowledge_base_branches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_app_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=True),
        sa.Column("knowledge_base_branch_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_branch_id"], ["knowledge_base_branches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_app_id", "knowledge_base_id", name="uq_project_app_kb_branches_app_kb"),
    )
    op.create_index(
        "ix_project_app_knowledge_base_branches_id",
        "project_app_knowledge_base_branches",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_project_app_knowledge_base_branches_project_app_id",
        "project_app_knowledge_base_branches",
        ["project_app_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_app_knowledge_base_branches_knowledge_base_id",
        "project_app_knowledge_base_branches",
        ["knowledge_base_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_app_knowledge_base_branches_branch_id",
        "project_app_knowledge_base_branches",
        ["knowledge_base_branch_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO project_app_knowledge_base_branches (
                project_app_id, knowledge_base_id, knowledge_base_branch_id, created_at
            )
            SELECT pakb.project_app_id, pakb.knowledge_base_id, kbb.id, pakb.created_at
            FROM project_app_knowledge_bases AS pakb
            JOIN knowledge_base_branches AS kbb
              ON kbb.knowledge_base_id = pakb.knowledge_base_id
             AND kbb.code = 'default'
            """
        )
    )

    op.drop_index("ix_project_app_knowledge_bases_knowledge_base_id", table_name="project_app_knowledge_bases")
    op.drop_index("ix_project_app_knowledge_bases_project_app_id", table_name="project_app_knowledge_bases")
    op.drop_index("ix_project_app_knowledge_bases_id", table_name="project_app_knowledge_bases")
    op.drop_table("project_app_knowledge_bases")
