"""Embedded assistant session and chat endpoints."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.embed import (
    EmbedTokenContext,
    get_embed_token_context,
    require_enterprise_service_token,
)
from app.application.kb_chat_service import get_kb_chat_service
from app.core.config import settings
from app.core.config.embed_pages import EmbedPageConfig, get_embed_page_config
from app.core.security import create_embed_token
from app.db.session import get_db
from app.models.schemas.kb_chat import (
    KbChatFeedbackRequest,
    KbChatResponse,
    KbChatSessionDetail,
    KbChatSessionSummary,
)
from app.models.schemas.project import (
    EmbedAssistantBootstrapResponse,
    EmbedAssistantChatRequest,
    EmbedPageConfigResponse,
    EmbedSessionCreate,
    EmbedSessionResponse,
)
from app.repositories.kb_chat_log_repository import KbChatLogRepository
from app.repositories.project_repository import ProjectAppRuntimeRecord, ProjectRepository

router = APIRouter()


async def _get_runtime_from_codes(
    *,
    db: AsyncSession,
    product_code: str,
    project_code: str,
    app_code: str,
) -> ProjectAppRuntimeRecord:
    runtime = await ProjectRepository(db).get_runtime_by_codes(
        product_code=product_code,
        project_code=project_code,
        app_code=app_code,
        active_only=True,
    )
    if runtime is None:
        raise HTTPException(status_code=404, detail="Active project application not found")
    return runtime


async def _get_runtime_from_context(
    *,
    db: AsyncSession,
    context: EmbedTokenContext,
) -> ProjectAppRuntimeRecord:
    runtime = await ProjectRepository(db).get_runtime_by_app_id(
        project_app_id=context.project_app_id,
        active_only=True,
    )
    if runtime is None or runtime.project.id != context.project_id:
        raise HTTPException(status_code=404, detail="Active project application not found")
    return runtime


def _build_embed_runtime_request(
    *,
    runtime: ProjectAppRuntimeRecord,
    context: EmbedTokenContext,
    query: str,
    session_id: str | None = None,
    page_context: dict | None = None,
    page_config: EmbedPageConfig | None = None,
) -> SimpleNamespace:
    assistant = runtime.assistant
    return SimpleNamespace(
        query=query,
        session_id=session_id,
        product_id=runtime.product.id,
        project_id=runtime.project.id,
        project_app_id=runtime.app.id,
        external_user_id=context.external_user_id,
        external_user_name=context.external_user_name,
        store_id=context.store_id,
        team_id=assistant.team_id,
        knowledge_base_id=runtime.app.knowledge_base_id,
        category_id=runtime.app.category_id,
        assistant_id=assistant.id,
        assistant_name=assistant.name,
        assistant_welcome_message=assistant.welcome_message,
        assistant_placeholder_text=assistant.placeholder_text,
        assistant_llm_model_key=assistant.llm_model_key,
        assistant_persona_prompt=assistant.persona_prompt,
        assistant_rule_template=assistant.rule_template,
        assistant_suggested_prompts=list(assistant.suggested_prompts or []),
        page_context=page_context,
        page_config=page_config.model_dump() if page_config is not None else None,
    )


def _page_config_response(config: EmbedPageConfig) -> EmbedPageConfigResponse:
    return EmbedPageConfigResponse(
        page_type=config.page_type,
        page_name=config.page_name,
        page_description=config.page_description,
        assistant_intro=config.assistant_intro,
        suggested_questions=list(config.suggested_questions or []),
    )


def _resolve_page_config(
    *,
    runtime: ProjectAppRuntimeRecord,
    page_type: str | None,
) -> EmbedPageConfig | None:
    return get_embed_page_config(
        runtime.product.code,
        runtime.project.code,
        runtime.app.code,
        page_type,
    )


def _build_page_context(
    *,
    runtime: ProjectAppRuntimeRecord,
    page_type: str | None,
) -> dict | None:
    if not page_type:
        return None
    return {
        "app_id": runtime.app.code,
        "page_type": page_type,
    }


def _resolve_embed_frontend_base_url(request: Request) -> str:
    configured = settings.EMBED_FRONTEND_BASE_URL.strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


@router.post(
    "/sessions",
    response_model=EmbedSessionResponse,
    dependencies=[Depends(require_enterprise_service_token)],
)
async def create_embed_session(
    body: EmbedSessionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    runtime = await _get_runtime_from_codes(
        db=db,
        product_code=body.product_code,
        project_code=body.project_code,
        app_code=body.app_code,
    )
    expires = max(1, settings.EMBED_TOKEN_EXPIRE_MINUTES)
    token = create_embed_token(
        project_id=runtime.project.id,
        project_app_id=runtime.app.id,
        external_user_id=body.external_user_id.strip(),
        external_user_name=(body.external_user_name or "").strip() or None,
        store_id=(body.store_id or "").strip() or None,
        initial_page_type=(body.initial_page_type or "").strip() or None,
        expires_delta=timedelta(minutes=expires),
    )
    base_url = _resolve_embed_frontend_base_url(request)
    embed_url = f"{base_url}/embed/assistant?{urlencode({'token': token})}"
    return EmbedSessionResponse(
        embed_url=embed_url,
        expires_in_seconds=expires * 60,
    )


@router.get("/assistant/bootstrap", response_model=EmbedAssistantBootstrapResponse)
async def embed_bootstrap(
    context: EmbedTokenContext = Depends(get_embed_token_context),
    db: AsyncSession = Depends(get_db),
):
    runtime = await _get_runtime_from_context(db=db, context=context)
    assistant = runtime.assistant
    page_config = _resolve_page_config(
        runtime=runtime,
        page_type=context.initial_page_type,
    )
    return EmbedAssistantBootstrapResponse(
        product_id=runtime.product.id,
        product_code=runtime.product.code,
        product_name=runtime.product.name,
        project_id=runtime.project.id,
        project_code=runtime.project.code,
        project_name=runtime.project.name,
        project_app_id=runtime.app.id,
        app_code=runtime.app.code,
        app_name=runtime.app.name,
        assistant_id=assistant.id,
        assistant_name=assistant.name,
        welcome_message=assistant.welcome_message,
        placeholder_text=assistant.placeholder_text,
        suggested_prompts=list(assistant.suggested_prompts or []),
        page_config=_page_config_response(page_config) if page_config is not None else None,
    )


@router.get("/assistant/sessions", response_model=list[KbChatSessionSummary])
async def list_embed_sessions(
    limit: int = 30,
    context: EmbedTokenContext = Depends(get_embed_token_context),
):
    return await get_kb_chat_service().list_sessions(
        user_id=None,
        limit=limit,
        project_app_id=context.project_app_id,
        external_user_id=context.external_user_id,
    )


@router.get("/assistant/sessions/{session_id}", response_model=KbChatSessionDetail)
async def get_embed_session(
    session_id: str,
    context: EmbedTokenContext = Depends(get_embed_token_context),
):
    session = await get_kb_chat_service().get_session(
        user_id=None,
        session_id=session_id,
        project_app_id=context.project_app_id,
        external_user_id=context.external_user_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.delete("/assistant/sessions/{session_id}", status_code=204)
async def delete_embed_session(
    session_id: str,
    context: EmbedTokenContext = Depends(get_embed_token_context),
):
    deleted = await get_kb_chat_service().delete_session(
        user_id=None,
        session_id=session_id,
        project_app_id=context.project_app_id,
        external_user_id=context.external_user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return None


@router.post("/assistant/invoke", response_model=KbChatResponse)
async def invoke_embed_assistant(
    body: EmbedAssistantChatRequest,
    context: EmbedTokenContext = Depends(get_embed_token_context),
    db: AsyncSession = Depends(get_db),
):
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    runtime = await _get_runtime_from_context(db=db, context=context)
    page_type = (
        body.page_context.page_type
        if body.page_context is not None
        else context.initial_page_type
    )
    page_config = _resolve_page_config(runtime=runtime, page_type=page_type)
    request = _build_embed_runtime_request(
        runtime=runtime,
        context=context,
        query=query,
        session_id=body.session_id,
        page_context=_build_page_context(runtime=runtime, page_type=page_type),
        page_config=page_config,
    )
    return await get_kb_chat_service().invoke(request, user_id=None)


@router.post("/assistant/stream")
async def stream_embed_assistant(
    body: EmbedAssistantChatRequest,
    context: EmbedTokenContext = Depends(get_embed_token_context),
    db: AsyncSession = Depends(get_db),
):
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    runtime = await _get_runtime_from_context(db=db, context=context)
    page_type = (
        body.page_context.page_type
        if body.page_context is not None
        else context.initial_page_type
    )
    page_config = _resolve_page_config(runtime=runtime, page_type=page_type)
    request = _build_embed_runtime_request(
        runtime=runtime,
        context=context,
        query=query,
        session_id=body.session_id,
        page_context=_build_page_context(runtime=runtime, page_type=page_type),
        page_config=page_config,
    )
    return StreamingResponse(
        get_kb_chat_service().stream(request, user_id=None),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/assistant/feedback/{log_id}")
async def submit_embed_feedback(
    log_id: int,
    body: KbChatFeedbackRequest,
    context: EmbedTokenContext = Depends(get_embed_token_context),
    db: AsyncSession = Depends(get_db),
):
    repo = KbChatLogRepository(db)
    existing = await repo.get_by_id(log_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="KB chat log not found")
    if (
        existing.project_app_id != context.project_app_id
        or existing.external_user_id != context.external_user_id
    ):
        raise HTTPException(status_code=403, detail="Cannot submit feedback for another user")
    await repo.submit_feedback(
        log_id=log_id,
        feedback_value=body.feedback_value,
        feedback_note=body.feedback_note,
    )
    return {"message": "Feedback saved"}
