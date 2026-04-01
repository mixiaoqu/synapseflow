"""Team and team-member repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Team, TeamMember


class TeamRepository:
    """Persists teams and their members."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def list_teams(self) -> list[Team]:
        result = await self.db.execute(
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == self.user_id)
            .order_by(Team.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_team(
        self,
        *,
        name: str,
        code: str | None = None,
        description: str | None = None,
    ) -> Team:
        team = Team(
            name=name.strip(),
            code=(code or "").strip() or None,
            description=(description or "").strip() or None,
        )
        self.db.add(team)
        await self.db.flush()
        self.db.add(TeamMember(team_id=team.id, user_id=self.user_id, role="owner"))
        await self.db.commit()
        await self.db.refresh(team)
        return team

    async def get_team(self, team_id: int) -> Team | None:
        result = await self.db.execute(
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(
                Team.id == team_id,
                TeamMember.user_id == self.user_id,
            )
        )
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
