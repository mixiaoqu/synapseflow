"""add content risk logs

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "5e6f7a8b9c0d"
down_revision = "4d5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_risk_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_log_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("project_app_id", sa.Integer(), nullable=True),
        sa.Column("external_user_id", sa.String(length=255), nullable=True),
        sa.Column("external_user_name", sa.String(length=255), nullable=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=True),
        sa.Column("assistant_id", sa.Integer(), nullable=True),
        sa.Column("scene", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("checked_text", sa.Text(), nullable=False),
        sa.Column("hits", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistant_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chat_log_id"], ["kb_chat_logs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_app_id"], ["project_apps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_risk_logs_id", "content_risk_logs", ["id"], unique=False)
    op.create_index("ix_content_risk_logs_chat_log_id", "content_risk_logs", ["chat_log_id"], unique=False)
    op.create_index("ix_content_risk_logs_user_id", "content_risk_logs", ["user_id"], unique=False)
    op.create_index("ix_content_risk_logs_session_id", "content_risk_logs", ["session_id"], unique=False)
    op.create_index("ix_content_risk_logs_product_id", "content_risk_logs", ["product_id"], unique=False)
    op.create_index("ix_content_risk_logs_project_id", "content_risk_logs", ["project_id"], unique=False)
    op.create_index("ix_content_risk_logs_project_app_id", "content_risk_logs", ["project_app_id"], unique=False)
    op.create_index("ix_content_risk_logs_external_user_id", "content_risk_logs", ["external_user_id"], unique=False)
    op.create_index("ix_content_risk_logs_knowledge_base_id", "content_risk_logs", ["knowledge_base_id"], unique=False)
    op.create_index("ix_content_risk_logs_assistant_id", "content_risk_logs", ["assistant_id"], unique=False)
    op.create_index("ix_content_risk_logs_scene", "content_risk_logs", ["scene"], unique=False)
    op.create_index("ix_content_risk_logs_action", "content_risk_logs", ["action"], unique=False)
    op.create_index("ix_content_risk_logs_blocked", "content_risk_logs", ["blocked"], unique=False)
    op.create_index("ix_content_risk_logs_risk_level", "content_risk_logs", ["risk_level"], unique=False)
    op.create_index("ix_content_risk_logs_created_at", "content_risk_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_content_risk_logs_created_at", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_risk_level", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_blocked", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_action", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_scene", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_assistant_id", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_knowledge_base_id", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_external_user_id", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_project_app_id", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_project_id", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_product_id", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_session_id", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_user_id", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_chat_log_id", table_name="content_risk_logs")
    op.drop_index("ix_content_risk_logs_id", table_name="content_risk_logs")
    op.drop_table("content_risk_logs")
