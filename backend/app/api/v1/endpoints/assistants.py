"""Assistant profile management and assistant-driven chat endpoints."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, require_content_roles
from app.application.assistant_service import AssistantService
from app.application.agent_chat_service import get_agent_chat_service
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.assistant import (
    AssistantAvailabilityResponse,
    AssistantBulkActionRequest,
    AssistantBulkActionResponse,
    AssistantDependencyUsageResponse,
    AssistantModelOptionsResponse,
    AssistantPreviewRequest,
    AssistantProfileCreate,
    AssistantProfileListResponse,
    AssistantProfileResponse,
    AssistantProfileSummary,
    AssistantProfileUpdate,
    AssistantReorderRequest,
)
from app.models.schemas.kb_chat import KbChatResponse

router = APIRouter()


def _build_runtime_request(
    *,
    assistant: AssistantProfileResponse,
    query: str,
    session_id: str | None,
) -> SimpleNamespace:
    knowledge_base_id = getattr(assistant, "knowledge_base_id", None)
    return SimpleNamespace(
        query=query,
        session_id=session_id,
        team_id=assistant.team_id,
        knowledge_base_id=knowledge_base_id,
        knowledge_base_ids=[knowledge_base_id] if knowledge_base_id is not None else [],
        category_id=getattr(assistant, "category_id", None),
        assistant_id=assistant.id,
        assistant_name=assistant.name,
        assistant_welcome_message=assistant.welcome_message,
        assistant_placeholder_text=assistant.placeholder_text,
        assistant_llm_model_key=assistant.llm_model_key,
        assistant_persona_prompt=assistant.persona_prompt,
        assistant_rule_template=assistant.rule_template,
        assistant_suggested_prompts=list(assistant.suggested_prompts or []),
    )


@router.get("", response_model=AssistantProfileListResponse)
async def list_assistants(
    team_id: int | None = Query(None),
    active_only: bool = Query(False),
    keyword: str | None = Query(None),
    status: str = Query("all", pattern="^(all|active|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.list_profiles_page(
        team_id=team_id,
        active_only=active_only,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=AssistantProfileResponse)
async def create_assistant(
    body: AssistantProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.create_profile(body)


@router.post("/reorder", response_model=list[AssistantProfileSummary])
async def reorder_assistants(
    body: AssistantReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.reorder_profiles(body)


@router.post("/bulk-action", response_model=AssistantBulkActionResponse)
async def bulk_action_assistants(
    body: AssistantBulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.bulk_action(body)


@router.get("/available", response_model=AssistantAvailabilityResponse)
async def list_available_assistants(
    team_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.list_available(
        team_id=team_id,
    )


@router.post("/preview", response_model=KbChatResponse)
async def preview_assistant(
    body: AssistantPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.preview_profile(body)


@router.get("/model-options", response_model=AssistantModelOptionsResponse)
async def list_assistant_model_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.list_model_options()


@router.get("/{assistant_id}/usage", response_model=AssistantDependencyUsageResponse)
async def get_assistant_usage(
    assistant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.get_dependency_usage(assistant_id)


@router.get("/{assistant_id}", response_model=AssistantProfileResponse)
async def get_assistant(
    assistant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.get_profile(assistant_id)


@router.put("/{assistant_id}", response_model=AssistantProfileResponse)
async def update_assistant(
    assistant_id: int,
    body: AssistantProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    return await service.update_profile(assistant_id, body)


@router.delete("/{assistant_id}")
async def delete_assistant(
    assistant_id: int,
    force: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    await service.delete_profile(assistant_id, force=force)
    return {"message": "Deleted successfully"}


@router.post("/{assistant_id}/invoke", response_model=KbChatResponse)
async def invoke_assistant(
    assistant_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = str(body.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    session_id = body.get("session_id")
    session_id = str(session_id).strip() if isinstance(session_id, str) else None
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    assistant = await service.get_profile(assistant_id, active_only=True)
    request = _build_runtime_request(
        assistant=assistant,
        query=query,
        session_id=session_id,
    )
    try:
        return await get_agent_chat_service().invoke(request, user_id=current_user.id)
    except Exception as exc:
        logger.exception("[Assistants] invoke failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{assistant_id}/stream")
async def stream_assistant(
    assistant_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = str(body.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    session_id = body.get("session_id")
    session_id = str(session_id).strip() if isinstance(session_id, str) else None
    service = AssistantService(db, user_id=current_user.id, user=current_user)
    assistant = await service.get_profile(assistant_id, active_only=True)
    request = _build_runtime_request(
        assistant=assistant,
        query=query,
        session_id=session_id,
    )
    return StreamingResponse(
        get_agent_chat_service().stream(request, user_id=current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
