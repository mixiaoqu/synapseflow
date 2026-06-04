"""Content-risk library persistence helpers."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ContentRiskLibrary, ContentRiskRule


class ContentRiskLibraryRepository:
    """Persist content-risk rule libraries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_libraries(
        self,
        *,
        keyword: str | None = None,
        enabled: bool | None = None,
    ) -> list[ContentRiskLibrary]:
        stmt = select(ContentRiskLibrary)
        if keyword:
            needle = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    ContentRiskLibrary.name.ilike(needle),
                    ContentRiskLibrary.description.ilike(needle),
                )
            )
        if enabled is not None:
            stmt = stmt.where(ContentRiskLibrary.enabled.is_(enabled))
        result = await self.db.execute(
            stmt.order_by(ContentRiskLibrary.created_at.desc(), ContentRiskLibrary.id.desc())
        )
        return list(result.scalars().all())

    async def get_library(self, library_id: int) -> ContentRiskLibrary | None:
        return await self.db.get(ContentRiskLibrary, library_id)

    async def name_exists(self, name: str, *, exclude_id: int | None = None) -> bool:
        stmt = select(ContentRiskLibrary).where(ContentRiskLibrary.name == name.strip())
        if exclude_id is not None:
            stmt = stmt.where(ContentRiskLibrary.id != exclude_id)
        result = await self.db.execute(stmt.limit(1))
        return result.scalar_one_or_none() is not None

    async def create_library(self, library: ContentRiskLibrary) -> ContentRiskLibrary:
        self.db.add(library)
        await self.db.commit()
        await self.db.refresh(library)
        return library

    async def update_library(self, library: ContentRiskLibrary) -> ContentRiskLibrary:
        await self.db.commit()
        await self.db.refresh(library)
        return library

    async def list_rules(
        self,
        library_id: int,
        *,
        keyword: str | None = None,
        enabled: bool | None = None,
    ) -> list[ContentRiskRule]:
        stmt = select(ContentRiskRule).where(ContentRiskRule.library_id == library_id)
        if keyword:
            needle = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    ContentRiskRule.name.ilike(needle),
                    ContentRiskRule.description.ilike(needle),
                    ContentRiskRule.pattern.ilike(needle),
                    ContentRiskRule.risk_category.ilike(needle),
                )
            )
        if enabled is not None:
            stmt = stmt.where(ContentRiskRule.enabled.is_(enabled))
        result = await self.db.execute(
            stmt.order_by(ContentRiskRule.created_at.desc(), ContentRiskRule.id.desc())
        )
        return list(result.scalars().all())

    async def list_enabled_rules_for_scene(self, scene: str) -> list[ContentRiskRule]:
        scene_column = (
            ContentRiskRule.applies_to_query
            if scene == "query"
            else ContentRiskRule.applies_to_answer
        )
        stmt = (
            select(ContentRiskRule)
            .join(ContentRiskLibrary, ContentRiskRule.library_id == ContentRiskLibrary.id)
            .where(
                ContentRiskLibrary.enabled.is_(True),
                ContentRiskRule.enabled.is_(True),
                scene_column.is_(True),
            )
            .order_by(ContentRiskRule.created_at.asc(), ContentRiskRule.id.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_rule(self, library_id: int, rule_id: int) -> ContentRiskRule | None:
        stmt = select(ContentRiskRule).where(
            ContentRiskRule.library_id == library_id,
            ContentRiskRule.id == rule_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def rule_name_exists(
        self,
        library_id: int,
        name: str,
        *,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = select(ContentRiskRule).where(
            ContentRiskRule.library_id == library_id,
            ContentRiskRule.name == name.strip(),
        )
        if exclude_id is not None:
            stmt = stmt.where(ContentRiskRule.id != exclude_id)
        result = await self.db.execute(stmt.limit(1))
        return result.scalar_one_or_none() is not None

    async def create_rule(
        self,
        *,
        library: ContentRiskLibrary,
        rule: ContentRiskRule,
    ) -> ContentRiskRule:
        library.rule_count += 1
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def update_rule(self, rule: ContentRiskRule) -> ContentRiskRule:
        await self.db.commit()
        await self.db.refresh(rule)
        return rule
