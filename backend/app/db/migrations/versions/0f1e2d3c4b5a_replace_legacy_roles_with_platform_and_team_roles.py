"""Replace legacy user roles with platform and team roles.

Revision ID: 0f1e2d3c4b5a
Revises: 7b8c9d0e1f2a
Create Date: 2026-06-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0f1e2d3c4b5a"
down_revision = "7b8c9d0e1f2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO teams (name, code, description, created_at, updated_at)
            SELECT '默认团队', 'default', '系统初始化默认团队', NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM teams WHERE code = 'default' OR name = '默认团队'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET role = CASE
                WHEN username = 'admin' THEN 'system_admin'
                ELSE 'user'
            END
            WHERE role NOT IN ('system_admin', 'system_operator', 'user')
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO team_members (team_id, user_id, role, created_at, updated_at)
            SELECT teams.id, users.id, 'owner', NOW(), NOW()
            FROM users
            JOIN teams ON teams.code = 'default'
            WHERE users.username = 'admin'
              AND NOT EXISTS (
                  SELECT 1
                  FROM team_members
                  WHERE team_members.team_id = teams.id
                    AND team_members.user_id = users.id
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE team_members
            SET role = 'owner'
            FROM users, teams
            WHERE users.username = 'admin'
              AND teams.code = 'default'
              AND team_members.user_id = users.id
              AND team_members.team_id = teams.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE team_members
            SET role = 'viewer'
            WHERE role NOT IN ('owner', 'admin', 'editor', 'reviewer', 'viewer')
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET role = 'user'
            WHERE role NOT IN ('system_admin', 'system_operator', 'user')
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE team_members
            SET role = 'viewer'
            WHERE role NOT IN ('owner', 'admin', 'editor', 'reviewer', 'viewer')
            """
        )
    )
