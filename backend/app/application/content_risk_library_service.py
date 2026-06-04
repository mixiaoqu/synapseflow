"""Content-risk library application service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ContentRiskLibrary, ContentRiskRule
from app.models.schemas.content_risk_library import (
    ContentRiskLibraryCreate,
    ContentRiskLibraryResponse,
    ContentRiskLibraryUpdate,
    ContentRiskRuleCreate,
    ContentRiskRuleResponse,
    ContentRiskRuleUpdate,
)
from app.repositories.content_risk_library_repository import ContentRiskLibraryRepository


class ContentRiskLibraryService:
    """Admin-facing content-risk rule library use cases."""

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None

    @staticmethod
    def _normalize_name(value: str) -> str:
        name = value.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Library name cannot be empty")
        return name

    @staticmethod
    def _normalize_required_text(value: str, *, field_name: str) -> str:
        text = value.strip()
        if not text:
            raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty")
        return text

    async def list_libraries(
        self,
        *,
        db: AsyncSession,
        keyword: str | None = None,
        enabled: bool | None = None,
    ) -> list[ContentRiskLibraryResponse]:
        rows = await ContentRiskLibraryRepository(db).list_libraries(keyword=keyword, enabled=enabled)
        return [ContentRiskLibraryResponse.model_validate(row) for row in rows]

    async def create_library(
        self,
        *,
        db: AsyncSession,
        payload: ContentRiskLibraryCreate,
        actor_user_id: int | None,
    ) -> ContentRiskLibraryResponse:
        repository = ContentRiskLibraryRepository(db)
        name = self._normalize_name(payload.name)
        if await repository.name_exists(name):
            raise HTTPException(status_code=400, detail="Rule library name already exists")
        library = ContentRiskLibrary(
            name=name,
            description=self._normalize_optional_text(payload.description),
            enabled=payload.enabled,
            created_by_user_id=actor_user_id,
            updated_by_user_id=actor_user_id,
        )
        row = await repository.create_library(library)
        return ContentRiskLibraryResponse.model_validate(row)

    async def update_library(
        self,
        library_id: int,
        *,
        db: AsyncSession,
        payload: ContentRiskLibraryUpdate,
        actor_user_id: int | None,
    ) -> ContentRiskLibraryResponse:
        repository = ContentRiskLibraryRepository(db)
        library = await repository.get_library(library_id)
        if library is None:
            raise HTTPException(status_code=404, detail="Rule library not found")
        name = self._normalize_name(payload.name)
        if await repository.name_exists(name, exclude_id=library_id):
            raise HTTPException(status_code=400, detail="Rule library name already exists")
        library.name = name
        library.description = self._normalize_optional_text(payload.description)
        library.enabled = payload.enabled
        library.updated_by_user_id = actor_user_id
        row = await repository.update_library(library)
        return ContentRiskLibraryResponse.model_validate(row)

    async def list_rules(
        self,
        library_id: int,
        *,
        db: AsyncSession,
        keyword: str | None = None,
        enabled: bool | None = None,
    ) -> list[ContentRiskRuleResponse]:
        repository = ContentRiskLibraryRepository(db)
        library = await repository.get_library(library_id)
        if library is None:
            raise HTTPException(status_code=404, detail="Rule library not found")
        rows = await repository.list_rules(library_id, keyword=keyword, enabled=enabled)
        return [ContentRiskRuleResponse.model_validate(row) for row in rows]

    async def create_rule(
        self,
        library_id: int,
        *,
        db: AsyncSession,
        payload: ContentRiskRuleCreate,
        actor_user_id: int | None,
    ) -> ContentRiskRuleResponse:
        repository = ContentRiskLibraryRepository(db)
        library = await repository.get_library(library_id)
        if library is None:
            raise HTTPException(status_code=404, detail="Rule library not found")
        name = self._normalize_required_text(payload.name, field_name="Rule name")
        if await repository.rule_name_exists(library_id, name):
            raise HTTPException(status_code=400, detail="Rule name already exists")
        rule = ContentRiskRule(
            library_id=library_id,
            name=name,
            description=self._normalize_optional_text(payload.description),
            rule_type=payload.rule_type,
            match_mode=payload.match_mode,
            pattern=self._normalize_required_text(payload.pattern, field_name="Rule pattern"),
            risk_category=self._normalize_required_text(payload.risk_category, field_name="Risk category"),
            risk_level=payload.risk_level,
            default_action=payload.default_action,
            applies_to_query=payload.applies_to_query,
            applies_to_answer=payload.applies_to_answer,
            enabled=payload.enabled,
            created_by_user_id=actor_user_id,
            updated_by_user_id=actor_user_id,
        )
        row = await repository.create_rule(library=library, rule=rule)
        return ContentRiskRuleResponse.model_validate(row)

    async def update_rule(
        self,
        library_id: int,
        rule_id: int,
        *,
        db: AsyncSession,
        payload: ContentRiskRuleUpdate,
        actor_user_id: int | None,
    ) -> ContentRiskRuleResponse:
        repository = ContentRiskLibraryRepository(db)
        library = await repository.get_library(library_id)
        if library is None:
            raise HTTPException(status_code=404, detail="Rule library not found")
        rule = await repository.get_rule(library_id, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Rule not found")
        name = self._normalize_required_text(payload.name, field_name="Rule name")
        if await repository.rule_name_exists(library_id, name, exclude_id=rule_id):
            raise HTTPException(status_code=400, detail="Rule name already exists")
        rule.name = name
        rule.description = self._normalize_optional_text(payload.description)
        rule.rule_type = payload.rule_type
        rule.match_mode = payload.match_mode
        rule.pattern = self._normalize_required_text(payload.pattern, field_name="Rule pattern")
        rule.risk_category = self._normalize_required_text(payload.risk_category, field_name="Risk category")
        rule.risk_level = payload.risk_level
        rule.default_action = payload.default_action
        rule.applies_to_query = payload.applies_to_query
        rule.applies_to_answer = payload.applies_to_answer
        rule.enabled = payload.enabled
        rule.updated_by_user_id = actor_user_id
        row = await repository.update_rule(rule)
        return ContentRiskRuleResponse.model_validate(row)
