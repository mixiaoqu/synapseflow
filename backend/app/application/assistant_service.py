"""Assistant profile application service."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AssistantProfile
from app.application.kb_chat_service import get_kb_chat_service
from app.models.schemas.assistant import (
    AssistantBulkActionRequest,
    AssistantBulkActionResponse,
    AssistantAvailabilityResponse,
    AssistantDependencyUsageResponse,
    AssistantProfileCreate,
    AssistantProfileResponse,
    AssistantReorderRequest,
    AssistantProfileSummary,
    AssistantProfileUpdate,
    AssistantPreviewRequest,
)
from app.repositories.assistant_profile_repository import (
    AssistantDependencyRecord,
    AssistantProfileRecord,
    AssistantProfileRepository,
)
from app.repositories.document_category_repository import DocumentCategoryRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.repositories.team_repository import TeamRepository
from app.services.document_lifecycle import (
    PREVIEW_ASK_DOCUMENT_STATUSES,
    RETRIEVAL_VERSION_CURRENT,
    RETRIEVAL_VERSION_LIVE,
    VISIBLE_ASK_DOCUMENT_STATUSES,
)


class AssistantService:
    """Encapsulates assistant profile validation and response mapping."""

    def __init__(self, db: AsyncSession, *, user_id: int):
        self.db = db
        self.user_id = user_id
        self.repository = AssistantProfileRepository(db, user_id=user_id)
        self.team_repository = TeamRepository(db, user_id=user_id)
        self.knowledge_base_repository = KnowledgeBaseRepository(db, user_id=user_id)
        self.category_repository = DocumentCategoryRepository(db, user_id=user_id)

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        normalized = (value or "").strip()
        return normalized or None

    @staticmethod
    def _normalize_prompt_list(values: list[str] | None) -> list[str]:
        normalized: list[str] = []
        for value in values or []:
            text = str(value or "").strip()
            if text:
                normalized.append(text)
        return normalized

    @staticmethod
    def _normalize_slug(slug: str) -> str:
        normalized = slug.strip().lower()
        if not normalized:
            raise HTTPException(status_code=400, detail="Assistant slug cannot be empty")
        return normalized

    @staticmethod
    def _to_summary(record: AssistantProfileRecord) -> AssistantProfileSummary:
        assistant = record.assistant
        return AssistantProfileSummary(
            id=assistant.id,
            name=assistant.name,
            slug=assistant.slug,
            team_id=assistant.team_id,
            team_name=record.team_name,
            knowledge_base_id=assistant.knowledge_base_id,
            knowledge_base_name=record.knowledge_base_name,
            category_id=assistant.category_id,
            category_name=record.category_name,
            created_by_user_id=assistant.created_by_user_id,
            created_by_name=record.created_by_name,
            description=assistant.description,
            welcome_message=assistant.welcome_message,
            placeholder_text=assistant.placeholder_text,
            suggested_prompts=list(assistant.suggested_prompts or []),
            is_active=assistant.is_active,
            sort_order=assistant.sort_order,
            created_at=assistant.created_at,
            updated_at=assistant.updated_at,
        )

    @classmethod
    def _to_response(cls, record: AssistantProfileRecord) -> AssistantProfileResponse:
        summary = cls._to_summary(record)
        assistant = record.assistant
        return AssistantProfileResponse(
            **summary.model_dump(),
            persona_prompt=assistant.persona_prompt,
            rule_template=assistant.rule_template,
        )

    @staticmethod
    def _to_dependency_usage(
        assistant_id: int,
        record: AssistantDependencyRecord,
    ) -> AssistantDependencyUsageResponse:
        return AssistantDependencyUsageResponse(
            assistant_id=assistant_id,
            active_session_count=record.active_session_count,
            related_log_count=record.related_log_count,
            has_dependencies=record.active_session_count > 0,
        )

    async def _get_records_by_ids(self, assistant_ids: list[int]) -> list[AssistantProfileRecord]:
        normalized_ids = [assistant_id for assistant_id in assistant_ids if assistant_id > 0]
        if not normalized_ids:
            raise HTTPException(status_code=400, detail="Assistant ids are required")
        unique_ids = list(dict.fromkeys(normalized_ids))
        records = await self.repository.list_by_ids(unique_ids)
        if len(records) != len(unique_ids):
            raise HTTPException(status_code=404, detail="One or more assistants were not found")
        return records

    async def _validate_scope(
        self,
        *,
        current_team_id: int,
        knowledge_base_id: int,
        category_id: int | None,
    ) -> tuple[object, object | None]:
        if not await self.team_repository.can_access_team(current_team_id):
            raise HTTPException(status_code=403, detail="Team access denied")

        knowledge_base = await self.knowledge_base_repository.get_by_id(knowledge_base_id)
        if knowledge_base is None:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        if knowledge_base.team_id != current_team_id:
            raise HTTPException(
                status_code=400,
                detail="Knowledge base does not belong to the current team",
            )

        category = None
        if category_id is not None:
            category = await self.category_repository.get_by_id(category_id)
            if category is None:
                raise HTTPException(status_code=404, detail="Category not found")
            if category.knowledge_base_id != knowledge_base_id:
                raise HTTPException(
                    status_code=400,
                    detail="Category does not belong to the selected knowledge base",
                )

        return knowledge_base, category

    async def list_profiles(
        self,
        *,
        team_id: int | None = None,
        knowledge_base_id: int | None = None,
        active_only: bool = False,
    ) -> list[AssistantProfileSummary]:
        records = await self.repository.list_profiles(
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            active_only=active_only,
        )
        return [self._to_summary(record) for record in records]

    async def list_available(
        self,
        *,
        team_id: int | None = None,
        knowledge_base_id: int | None = None,
    ) -> AssistantAvailabilityResponse:
        items = await self.list_profiles(
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            active_only=True,
        )
        return AssistantAvailabilityResponse(items=items)

    async def get_profile(
        self,
        assistant_id: int,
        *,
        active_only: bool = False,
    ) -> AssistantProfileResponse:
        record = await self.repository.get_by_id(assistant_id, active_only=active_only)
        if record is None:
            raise HTTPException(status_code=404, detail="Assistant not found")
        return self._to_response(record)

    async def create_profile(self, payload: AssistantProfileCreate) -> AssistantProfileResponse:
        knowledge_base, _ = await self._validate_scope(
            current_team_id=payload.current_team_id,
            knowledge_base_id=payload.knowledge_base_id,
            category_id=payload.category_id,
        )

        slug = self._normalize_slug(payload.slug)
        if await self.repository.slug_exists(slug):
            raise HTTPException(status_code=400, detail="Assistant slug already exists")

        assistant = AssistantProfile(
            name=payload.name.strip(),
            slug=slug,
            team_id=knowledge_base.team_id,
            knowledge_base_id=payload.knowledge_base_id,
            category_id=payload.category_id,
            created_by_user_id=self.user_id,
            description=self._normalize_optional_text(payload.description),
            welcome_message=self._normalize_optional_text(payload.welcome_message),
            placeholder_text=self._normalize_optional_text(payload.placeholder_text),
            persona_prompt=self._normalize_optional_text(payload.persona_prompt),
            rule_template=self._normalize_optional_text(payload.rule_template),
            suggested_prompts=self._normalize_prompt_list(payload.suggested_prompts),
            is_active=payload.is_active,
            sort_order=payload.sort_order,
        )
        await self.repository.create(assistant)
        record = await self.repository.get_by_id(assistant.id)
        if record is None:
            raise HTTPException(status_code=500, detail="Assistant creation failed")
        return self._to_response(record)

    async def update_profile(
        self,
        assistant_id: int,
        payload: AssistantProfileUpdate,
    ) -> AssistantProfileResponse:
        record = await self.repository.get_by_id(assistant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Assistant not found")

        knowledge_base, _ = await self._validate_scope(
            current_team_id=payload.current_team_id,
            knowledge_base_id=payload.knowledge_base_id,
            category_id=payload.category_id,
        )

        slug = self._normalize_slug(payload.slug)
        if await self.repository.slug_exists(slug, exclude_id=assistant_id):
            raise HTTPException(status_code=400, detail="Assistant slug already exists")

        assistant = record.assistant
        assistant.name = payload.name.strip()
        assistant.slug = slug
        assistant.team_id = knowledge_base.team_id
        assistant.knowledge_base_id = payload.knowledge_base_id
        assistant.category_id = payload.category_id
        assistant.description = self._normalize_optional_text(payload.description)
        assistant.welcome_message = self._normalize_optional_text(payload.welcome_message)
        assistant.placeholder_text = self._normalize_optional_text(payload.placeholder_text)
        assistant.persona_prompt = self._normalize_optional_text(payload.persona_prompt)
        assistant.rule_template = self._normalize_optional_text(payload.rule_template)
        assistant.suggested_prompts = self._normalize_prompt_list(payload.suggested_prompts)
        assistant.is_active = payload.is_active
        assistant.sort_order = payload.sort_order
        await self.repository.update(assistant)

        next_record = await self.repository.get_by_id(assistant_id)
        if next_record is None:
            raise HTTPException(status_code=500, detail="Assistant update failed")
        return self._to_response(next_record)

    async def get_dependency_usage(self, assistant_id: int) -> AssistantDependencyUsageResponse:
        record = await self.repository.get_by_id(assistant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Assistant not found")
        usage = await self.repository.get_dependency_usage(assistant_id)
        return self._to_dependency_usage(assistant_id, usage)

    async def preview_profile(self, payload: AssistantPreviewRequest):
        knowledge_base, _ = await self._validate_scope(
            current_team_id=payload.current_team_id,
            knowledge_base_id=payload.knowledge_base_id,
            category_id=payload.category_id,
        )
        allowed_statuses = (
            list(PREVIEW_ASK_DOCUMENT_STATUSES)
            if payload.include_unpublished
            else list(VISIBLE_ASK_DOCUMENT_STATUSES)
        )
        runtime_request = SimpleNamespace(
            query=payload.query.strip(),
            team_id=knowledge_base.team_id,
            knowledge_base_id=payload.knowledge_base_id,
            category_id=payload.category_id,
            assistant_id=None,
            assistant_name=self._normalize_optional_text(payload.name) or "预览助手",
            assistant_welcome_message=self._normalize_optional_text(payload.welcome_message),
            assistant_placeholder_text=self._normalize_optional_text(payload.placeholder_text),
            assistant_persona_prompt=self._normalize_optional_text(payload.persona_prompt),
            assistant_rule_template=self._normalize_optional_text(payload.rule_template),
            assistant_suggested_prompts=self._normalize_prompt_list(payload.suggested_prompts),
            allowed_document_statuses=allowed_statuses,
            retrieval_version_mode=(
                RETRIEVAL_VERSION_CURRENT
                if payload.include_unpublished
                else RETRIEVAL_VERSION_LIVE
            ),
            session_id=None,
        )
        return await get_kb_chat_service().preview(runtime_request, user_id=self.user_id)

    async def delete_profile(self, assistant_id: int, *, force: bool = False) -> None:
        record = await self.repository.get_by_id(assistant_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Assistant not found")
        usage = await self.repository.get_dependency_usage(assistant_id)
        if usage.active_session_count > 0 and not force:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Assistant is still referenced by {usage.active_session_count} "
                    "project assistant simulation session(s)"
                ),
            )
        await self.repository.delete(record.assistant)

    async def reorder_profiles(
        self,
        payload: AssistantReorderRequest,
    ) -> list[AssistantProfileSummary]:
        records = await self._get_records_by_ids(payload.assistant_ids)
        team_ids = {record.assistant.team_id for record in records}
        if len(team_ids) > 1:
            raise HTTPException(status_code=400, detail="Assistants must belong to the same team")

        for index, record in enumerate(records):
            record.assistant.sort_order = index

        await self.db.commit()
        refreshed = await self.repository.list_by_ids(payload.assistant_ids)
        return [self._to_summary(record) for record in refreshed]

    async def bulk_action(
        self,
        payload: AssistantBulkActionRequest,
    ) -> AssistantBulkActionResponse:
        records = await self._get_records_by_ids(payload.assistant_ids)
        assistants = [record.assistant for record in records]
        assistant_ids = [assistant.id for assistant in assistants]

        if payload.action == "enable":
            for assistant in assistants:
                assistant.is_active = True
            await self.db.commit()
        elif payload.action == "disable":
            for assistant in assistants:
                assistant.is_active = False
            await self.db.commit()
        else:
            dependency_map = await self.repository.get_dependency_usage_map(assistant_ids)
            blocked_ids = [
                assistant_id
                for assistant_id, usage in dependency_map.items()
                if usage.active_session_count > 0
            ]
            if blocked_ids and not payload.force:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Some assistants are still referenced by active assistant simulation "
                        f"sessions: {', '.join(str(item) for item in blocked_ids)}"
                    ),
                )
            for assistant in assistants:
                await self.db.delete(assistant)
            await self.db.commit()

        return AssistantBulkActionResponse(
            action=payload.action,
            affected_ids=assistant_ids,
            affected_count=len(assistant_ids),
        )
