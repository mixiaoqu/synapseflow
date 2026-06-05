"""Assistant profile persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssistantProfile,
    ChatSession,
    KbChatLog,
    Team,
    User,
)
from app.repositories.access_scope import accessible_assistant_profile_condition


@dataclass(slots=True)
class AssistantProfileRecord:
    """Assistant profile row plus resolved display names."""

    assistant: AssistantProfile
    team_name: str | None
    created_by_name: str | None


@dataclass(slots=True)
class AssistantDependencyRecord:
    """Persisted usage counts that reference one assistant profile."""

    active_session_count: int
    related_log_count: int


class AssistantProfileRepository:
    """Persist assistant profiles with team-scoped visibility."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    def _base_stmt(self):
        return (
            select(
                AssistantProfile,
                Team.name.label("team_name"),
                func.coalesce(User.full_name, User.username).label("created_by_name"),
            )
            .join(Team, Team.id == AssistantProfile.team_id)
            .outerjoin(User, User.id == AssistantProfile.created_by_user_id)
            .where(accessible_assistant_profile_condition(self.user_id))
        )

    @staticmethod
    def _to_record(row) -> AssistantProfileRecord:
        assistant, team_name, created_by_name = row
        return AssistantProfileRecord(
            assistant=assistant,
            team_name=team_name,
            created_by_name=created_by_name,
        )

    async def list_profiles(
        self,
        *,
        team_id: int | None = None,
        active_only: bool = False,
    ) -> list[AssistantProfileRecord]:
        return await self.list_profiles_page(
            team_id=team_id,
            active_only=active_only,
            offset=0,
            limit=None,
        )

    async def count_profiles(
        self,
        *,
        team_id: int | None = None,
        active_only: bool = False,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(AssistantProfile)
            .where(accessible_assistant_profile_condition(self.user_id))
        )
        if team_id is not None:
            stmt = stmt.where(AssistantProfile.team_id == team_id)
        if active_only:
            stmt = stmt.where(AssistantProfile.is_active.is_(True))
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    AssistantProfile.name.ilike(pattern),
                    AssistantProfile.slug.ilike(pattern),
                    AssistantProfile.description.ilike(pattern),
                )
            )
        if is_active is not None:
            stmt = stmt.where(AssistantProfile.is_active.is_(is_active))
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def list_profiles_page(
        self,
        *,
        team_id: int | None = None,
        active_only: bool = False,
        keyword: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AssistantProfileRecord]:
        stmt = self._base_stmt()
        if team_id is not None:
            stmt = stmt.where(AssistantProfile.team_id == team_id)
        if active_only:
            stmt = stmt.where(AssistantProfile.is_active.is_(True))
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    AssistantProfile.name.ilike(pattern),
                    AssistantProfile.slug.ilike(pattern),
                    AssistantProfile.description.ilike(pattern),
                )
            )
        if is_active is not None:
            stmt = stmt.where(AssistantProfile.is_active.is_(is_active))
        stmt = stmt.order_by(
            AssistantProfile.sort_order.asc(),
            AssistantProfile.created_at.desc(),
            AssistantProfile.id.desc(),
        )
        if limit is not None:
            stmt = stmt.offset(offset).limit(limit)
        rows = await self.db.execute(stmt)
        return [self._to_record(row) for row in rows.all()]

    async def list_by_ids(self, assistant_ids: list[int]) -> list[AssistantProfileRecord]:
        if not assistant_ids:
            return []
        stmt = self._base_stmt().where(AssistantProfile.id.in_(assistant_ids))
        rows = await self.db.execute(stmt)
        records = [self._to_record(row) for row in rows.all()]
        order_lookup = {assistant_id: index for index, assistant_id in enumerate(assistant_ids)}
        return sorted(records, key=lambda item: order_lookup.get(item.assistant.id, len(order_lookup)))

    async def get_by_id(
        self,
        assistant_id: int,
        *,
        active_only: bool = False,
    ) -> AssistantProfileRecord | None:
        stmt = self._base_stmt().where(AssistantProfile.id == assistant_id)
        if active_only:
            stmt = stmt.where(AssistantProfile.is_active.is_(True))
        row = (await self.db.execute(stmt)).one_or_none()
        return self._to_record(row) if row else None

    async def slug_exists(
        self,
        slug: str,
        *,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = select(func.count()).select_from(AssistantProfile).where(
            func.lower(AssistantProfile.slug) == slug.strip().lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(AssistantProfile.id != exclude_id)
        count = (await self.db.execute(stmt)).scalar() or 0
        return bool(count)

    async def create(self, assistant: AssistantProfile) -> AssistantProfile:
        self.db.add(assistant)
        await self.db.commit()
        await self.db.refresh(assistant)
        return assistant

    async def update(self, assistant: AssistantProfile) -> AssistantProfile:
        await self.db.commit()
        await self.db.refresh(assistant)
        return assistant

    async def delete(self, assistant: AssistantProfile) -> None:
        await self.db.delete(assistant)
        await self.db.commit()

    async def get_dependency_usage(self, assistant_id: int) -> AssistantDependencyRecord:
        session_count_stmt = select(func.count()).select_from(ChatSession).where(
            ChatSession.assistant_id == assistant_id,
        )
        log_count_stmt = select(func.count()).select_from(KbChatLog).where(
            KbChatLog.assistant_id == assistant_id,
        )
        active_session_count = int((await self.db.execute(session_count_stmt)).scalar() or 0)
        related_log_count = int((await self.db.execute(log_count_stmt)).scalar() or 0)
        return AssistantDependencyRecord(
            active_session_count=active_session_count,
            related_log_count=related_log_count,
        )

    async def get_dependency_usage_map(
        self,
        assistant_ids: list[int],
    ) -> dict[int, AssistantDependencyRecord]:
        if not assistant_ids:
            return {}

        session_stmt = (
            select(ChatSession.assistant_id, func.count())
            .where(ChatSession.assistant_id.in_(assistant_ids))
            .group_by(ChatSession.assistant_id)
        )
        log_stmt = (
            select(KbChatLog.assistant_id, func.count())
            .where(KbChatLog.assistant_id.in_(assistant_ids))
            .group_by(KbChatLog.assistant_id)
        )

        session_rows = (await self.db.execute(session_stmt)).all()
        log_rows = (await self.db.execute(log_stmt)).all()
        session_counts = {
            int(assistant_id): int(count)
            for assistant_id, count in session_rows
            if assistant_id is not None
        }
        log_counts = {
            int(assistant_id): int(count)
            for assistant_id, count in log_rows
            if assistant_id is not None
        }

        return {
            assistant_id: AssistantDependencyRecord(
                active_session_count=session_counts.get(assistant_id, 0),
                related_log_count=log_counts.get(assistant_id, 0),
            )
            for assistant_id in assistant_ids
        }
