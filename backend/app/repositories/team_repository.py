"""Team and team-member repository."""

from collections.abc import Sequence

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeBase, KnowledgeBaseMember, Team, TeamMember


class TeamRepository:
    """Persists teams and their members."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def list_teams(self) -> list[Team]:
        result = await self.db.execute(select(Team).order_by(Team.created_at.desc(), Team.id.desc()))
        return list(result.scalars().all())

    async def list_teams_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[Team], int]:
        """分页查询团队列表，支持按名称/编码模糊搜索。

        Args:
            page: 页码，从 1 开始
            page_size: 每页条数
            keyword: 可选搜索关键词，匹配 name 或 code

        Returns:
            (团队列表, 总数) 二元组
        """
        base_query = select(Team)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            base_query = base_query.where(
                or_(
                    Team.name.ilike(pattern),
                    Team.code.ilike(pattern),
                )
            )

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.db.execute(
            base_query.order_by(Team.created_at.desc(), Team.id.desc()).offset(offset).limit(page_size)
        )
        rows = list(result.scalars().all())
        return rows, total

    async def list_user_teams(self) -> list[Team]:
        """List teams visible to the current user for scoped operations."""
        result = await self.db.execute(
            select(Team)
            .outerjoin(TeamMember, TeamMember.team_id == Team.id)
            .outerjoin(KnowledgeBase, KnowledgeBase.team_id == Team.id)
            .where(
                or_(
                    TeamMember.user_id == self.user_id,
                    KnowledgeBase.user_id == self.user_id,
                    exists(
                        select(1)
                        .select_from(KnowledgeBaseMember)
                        .join(KnowledgeBase, KnowledgeBaseMember.knowledge_base_id == KnowledgeBase.id)
                        .where(
                            KnowledgeBase.team_id == Team.id,
                            KnowledgeBaseMember.user_id == self.user_id,
                        )
                        .correlate(Team)
                    ),
                )
            )
            .group_by(Team.id)
            .order_by(Team.created_at.desc(), Team.id.desc())
        )
        return list(result.scalars().all())

    async def can_access_team(self, team_id: int) -> bool:
        """Return whether the current user can access the given team."""
        result = await self.db.execute(
            select(Team.id)
            .outerjoin(TeamMember, TeamMember.team_id == Team.id)
            .outerjoin(KnowledgeBase, KnowledgeBase.team_id == Team.id)
            .where(
                Team.id == team_id,
                or_(
                    TeamMember.user_id == self.user_id,
                    KnowledgeBase.user_id == self.user_id,
                    exists(
                        select(1)
                        .select_from(KnowledgeBaseMember)
                        .join(KnowledgeBase, KnowledgeBaseMember.knowledge_base_id == KnowledgeBase.id)
                        .where(
                            KnowledgeBase.team_id == Team.id,
                            KnowledgeBaseMember.user_id == self.user_id,
                        )
                        .correlate(Team)
                    ),
                ),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def is_code_taken(self, code: str | None, *, exclude_team_id: int | None = None) -> bool:
        normalized = (code or "").strip()
        if not normalized:
            return False
        query = select(Team.id).where(Team.code == normalized)
        if exclude_team_id is not None:
            query = query.where(Team.id != exclude_team_id)
        result = await self.db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def create_team(
        self,
        *,
        name: str,
        code: str | None = None,
        description: str | None = None,
        member_ids: list[int] | None = None,
    ) -> Team:
        team = Team(
            name=name.strip(),
            code=(code or "").strip() or None,
            description=(description or "").strip() or None,
        )
        self.db.add(team)
        await self.db.flush()
        self.db.add(TeamMember(team_id=team.id, user_id=self.user_id, role="owner"))
        if member_ids:
            for uid in member_ids:
                if uid != self.user_id:
                    self.db.add(TeamMember(team_id=team.id, user_id=uid, role="member"))
        await self.db.commit()
        await self.db.refresh(team)
        return team

    async def get_team(self, team_id: int) -> Team | None:
        result = await self.db.execute(select(Team).where(Team.id == team_id))
        return result.scalar_one_or_none()

    async def update_team(
        self,
        team_id: int,
        *,
        name: str,
        code: str | None = None,
        description: str | None = None,
    ) -> Team | None:
        team = await self.get_team(team_id)
        if not team:
            return None
        team.name = name.strip()
        team.code = (code or "").strip() or None
        team.description = (description or "").strip() or None
        await self.db.commit()
        await self.db.refresh(team)
        return team

    async def delete_team(self, team_id: int) -> bool:
        team = await self.get_team(team_id)
        if not team:
            return False
        await self.db.delete(team)
        await self.db.commit()
        return True

    async def delete_teams(self, team_ids: Sequence[int]) -> int:
        unique_ids = list(dict.fromkeys(team_ids))
        if not unique_ids:
            return 0
        result = await self.db.execute(select(Team).where(Team.id.in_(unique_ids)))
        teams = list(result.scalars().all())
        for team in teams:
            await self.db.delete(team)
        await self.db.commit()
        return len(teams)

    async def list_members(self, team_id: int) -> list[TeamMember]:
        team = await self.get_team(team_id)
        if not team:
            return []
        result = await self.db.execute(
            select(TeamMember)
            .where(TeamMember.team_id == team_id)
            .order_by(TeamMember.created_at.asc())
        )
        return list(result.scalars().all())

    async def add_member(self, team_id: int, *, user_id: int, role: str) -> TeamMember | None:
        team = await self.get_team(team_id)
        if not team:
            return None

        result = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if member:
            member.role = role
        else:
            member = TeamMember(team_id=team_id, user_id=user_id, role=role)
            self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def update_member(self, team_id: int, *, user_id: int, role: str) -> TeamMember | None:
        team = await self.get_team(team_id)
        if not team:
            return None

        result = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return None
        member.role = role
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def update_members_role(
        self,
        team_id: int,
        *,
        user_ids: Sequence[int],
        role: str,
    ) -> int:
        team = await self.get_team(team_id)
        if not team:
            return 0

        unique_ids = list(dict.fromkeys(user_ids))
        if not unique_ids:
            return 0
        result = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id.in_(unique_ids),
            )
        )
        members = list(result.scalars().all())
        for member in members:
            member.role = role
        await self.db.commit()
        return len(members)

    async def delete_member(self, team_id: int, *, user_id: int) -> bool:
        team = await self.get_team(team_id)
        if not team:
            return False

        result = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return False
        await self.db.delete(member)
        await self.db.commit()
        return True

    async def delete_members(self, team_id: int, *, user_ids: Sequence[int]) -> int:
        team = await self.get_team(team_id)
        if not team:
            return 0

        unique_ids = list(dict.fromkeys(user_ids))
        if not unique_ids:
            return 0
        result = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id.in_(unique_ids),
            )
        )
        members = list(result.scalars().all())
        for member in members:
            await self.db.delete(member)
        await self.db.commit()
        return len(members)
