"""Add team scope to content-risk logs.

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-06-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "2b3c4d5e6f7a"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_risk_logs", sa.Column("team_id", sa.Integer(), nullable=True))
    op.create_index("ix_content_risk_logs_team_id", "content_risk_logs", ["team_id"], unique=False)
    op.create_foreign_key(
        "fk_content_risk_logs_team_id_teams",
        "content_risk_logs",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        sa.text(
            """
            UPDATE content_risk_logs AS logs
            SET team_id = COALESCE(kb.team_id, assistant.team_id, project.team_id, app_project.team_id, product.team_id)
            FROM content_risk_logs AS source
            LEFT JOIN knowledge_bases AS kb ON source.knowledge_base_id = kb.id
            LEFT JOIN assistant_profiles AS assistant ON source.assistant_id = assistant.id
            LEFT JOIN projects AS project ON source.project_id = project.id
            LEFT JOIN project_apps AS app ON source.project_app_id = app.id
            LEFT JOIN projects AS app_project ON app.project_id = app_project.id
            LEFT JOIN products AS product ON source.product_id = product.id
            WHERE logs.id = source.id
              AND logs.team_id IS NULL
              AND COALESCE(kb.team_id, assistant.team_id, project.team_id, app_project.team_id, product.team_id) IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_content_risk_logs_team_id_teams", "content_risk_logs", type_="foreignkey")
    op.drop_index("ix_content_risk_logs_team_id", table_name="content_risk_logs")
    op.drop_column("content_risk_logs", "team_id")
