"""Production embedded-agent use-case orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.agent.conversation_service import AgentConversationService
from app.application.agent.input_builder import AgentRunRequest
from app.application.agent.run_service import get_agent_run_service
from app.core.config.assistant_pages import AssistantPageConfig, get_assistant_page_config
from app.models.schemas.kb_chat import KbChatFeedbackRequest
from app.models.schemas.widget import (
    WidgetBootstrapResponse,
    WidgetChatRequest,
    WidgetPageConfigResponse,
)
from app.repositories.kb_chat_log_repository import KbChatLogRepository
from app.repositories.project_repository import ProjectAppRuntimeRecord, ProjectRepository


@dataclass(frozen=True, slots=True)
class EmbeddedAgentContext:
    team_id: int
    product_id: int
    project_id: int
    project_app_id: int
    external_user_id: str
    external_user_name: str | None
    trusted_scope: dict
    store_id: str | None
    initial_page_type: str | None


class EmbeddedAgentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ProjectRepository(db)
        self.run_service = get_agent_run_service()
        self.conversation_service = AgentConversationService()

    async def get_runtime(self, context: EmbeddedAgentContext) -> ProjectAppRuntimeRecord:
        runtime = await self.repository.get_runtime_by_app_id(
            project_app_id=context.project_app_id,
            active_only=True,
        )
        if runtime is None or runtime.project.id != context.project_id:
            raise HTTPException(status_code=404, detail="Active project application not found")
        return runtime

    @staticmethod
    def _resolve_page_config(
        runtime: ProjectAppRuntimeRecord,
        page_type: str | None,
    ) -> AssistantPageConfig | None:
        return get_assistant_page_config(
            runtime.product.code,
            runtime.project.code,
            runtime.app.code,
            page_type,
        )

    @staticmethod
    def _page_config_response(config: AssistantPageConfig) -> WidgetPageConfigResponse:
        return WidgetPageConfigResponse(
            page_type=config.page_type,
            page_name=config.page_name,
            page_description=config.page_description,
            assistant_intro=config.assistant_intro,
            suggested_questions=list(config.suggested_questions or []),
        )

    async def bootstrap(
        self,
        context: EmbeddedAgentContext,
        page_type: str | None,
    ) -> WidgetBootstrapResponse:
        runtime = await self.get_runtime(context)
        assistant = runtime.assistant
        resolved_page_type = (page_type or "").strip() or context.initial_page_type
        page_config = self._resolve_page_config(runtime, resolved_page_type)
        return WidgetBootstrapResponse(
            project_name=runtime.project.name,
            app_name=runtime.app.name,
            assistant_name=assistant.name,
            welcome_message=assistant.welcome_message,
            placeholder_text=assistant.placeholder_text,
            suggested_prompts=list(assistant.suggested_prompts or []),
            page_config=(
                self._page_config_response(page_config) if page_config is not None else None
            ),
        )

    async def list_sessions(self, context: EmbeddedAgentContext, limit: int):
        return await self.conversation_service.list_sessions(
            user_id=None,
            limit=limit,
            project_app_id=context.project_app_id,
            external_user_id=context.external_user_id,
        )

    async def get_session(self, context: EmbeddedAgentContext, session_id: str):
        session = await self.conversation_service.get_session(
            user_id=None,
            session_id=session_id,
            project_app_id=context.project_app_id,
            external_user_id=context.external_user_id,
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session

    async def delete_session(self, context: EmbeddedAgentContext, session_id: str) -> None:
        deleted = await self.conversation_service.delete_session(
            user_id=None,
            session_id=session_id,
            project_app_id=context.project_app_id,
            external_user_id=context.external_user_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Chat session not found")

    async def stream(self, context: EmbeddedAgentContext, payload: WidgetChatRequest):
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        runtime = await self.get_runtime(context)
        page_context = payload.page_context.model_dump(exclude_none=True)
        page_context["app_id"] = runtime.app.code
        page_config = self._resolve_page_config(runtime, payload.page_context.page_type)
        assistant = runtime.assistant
        request = AgentRunRequest(
            query=query,
            session_id=payload.session_id,
            product_id=runtime.product.id,
            project_id=runtime.project.id,
            project_app_id=runtime.app.id,
            external_user_id=context.external_user_id,
            external_user_name=context.external_user_name,
            store_id=context.store_id,
            trusted_scope=dict(context.trusted_scope),
            team_id=assistant.team_id,
            knowledge_base_id=runtime.app.knowledge_base_id,
            category_id=runtime.app.category_id,
            assistant_id=assistant.id,
            assistant_name=assistant.name,
            assistant_llm_model_key=assistant.llm_model_key,
            assistant_persona_prompt=assistant.persona_prompt,
            assistant_rule_template=assistant.rule_template,
            page_context=page_context,
            page_config=page_config.model_dump() if page_config is not None else None,
            source_surface="widget",
        )
        return self.run_service.stream(request, user_id=None)

    async def submit_feedback(
        self,
        context: EmbeddedAgentContext,
        log_id: int,
        payload: KbChatFeedbackRequest,
    ) -> None:
        repository = KbChatLogRepository(self.db)
        existing = await repository.get_by_id(log_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="KB chat log not found")
        if (
            existing.project_app_id != context.project_app_id
            or existing.external_user_id != context.external_user_id
        ):
            raise HTTPException(status_code=403, detail="Cannot submit feedback for another user")
        await repository.submit_feedback(
            log_id=log_id,
            feedback_value=payload.feedback_value,
            feedback_note=payload.feedback_note,
        )
