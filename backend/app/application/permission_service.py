"""Centralized platform and team permission checks."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import (
    PERMISSION_VIEW_TEAM_RESOURCE,
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_OPERATOR,
    has_team_role_permission,
    normalize_system_role,
    normalize_team_role,
)
from app.db.models import TeamMember, User


class PermissionService:
    """Resolves permissions from platform role and team membership."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def is_system_admin(user: User) -> bool:
        return normalize_system_role(getattr(user, "role", None)) == SYSTEM_ROLE_ADMIN

    @staticmethod
    def is_system_operator(user: User) -> bool:
        return normalize_system_role(getattr(user, "role", None)) == SYSTEM_ROLE_OPERATOR

    @classmethod
    def can_view_all_teams(cls, user: User) -> bool:
        return cls.is_system_admin(user)

    async def get_team_role(self, user: User, team_id: int) -> str | None:
        result = await self.db.execute(
            select(TeamMember.role).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user.id,
            )
        )
        role = result.scalar_one_or_none()
        return normalize_team_role(role) if role else None

    async def list_accessible_team_ids(self, user: User) -> list[int] | None:
        if self.can_view_all_teams(user):
            return None
        result = await self.db.execute(
            select(TeamMember.team_id)
            .where(TeamMember.user_id == user.id)
            .order_by(TeamMember.team_id.asc())
        )
        return list(result.scalars().all())

    async def can_access_team(self, user: User, team_id: int) -> bool:
        if self.can_view_all_teams(user):
            return True
        role = await self.get_team_role(user, team_id)
        return role is not None and has_team_role_permission(role, PERMISSION_VIEW_TEAM_RESOURCE)

    async def has_team_permission(self, user: User, team_id: int, permission: str) -> bool:
        if self.is_system_admin(user):
            return True
        role = await self.get_team_role(user, team_id)
        return role is not None and has_team_role_permission(role, permission)

    async def has_any_team_permission(
        self,
        user: User,
        team_ids: Sequence[int],
        permission: str,
    ) -> bool:
        if self.is_system_admin(user):
            return True
        for team_id in dict.fromkeys(team_ids):
            if await self.has_team_permission(user, int(team_id), permission):
                return True
        return False
