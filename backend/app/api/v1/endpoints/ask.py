"""End-user ask API built on top of KB chat service."""

from __future__ import annotations

from datetime import date, datetime, time
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, require_review_roles
from app.application.permission_service import PermissionService
from app.application.kb_chat_service import get_kb_chat_service
from app.core.authz import PERMISSION_REVIEW_QA_LOG, PERMISSION_VIEW_QA_LOG
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.kb_chat import (
    KbChatDiagnosticDoc,
    KbChatDiagnosticMessage,
    KbChatFeedbackRequest,
    KbChatLogDetail,
    KbChatLogItem,
    KbChatLogListResponse,
    KbChatPreviewRequest,
    KbChatRequest,
    KbChatResponse,
    KbChatRetrievalFunnel,
    KbChatRetrievalFunnelStage,
    KbChatRetrievalQueryStat,
    KbChatReviewRequest,
    KbChatSessionDetail,
    KbChatSessionSummary,
)
from app.models.schemas.team import TeamResponse
from app.repositories.kb_chat_log_repository import KbChatLogRepository
from app.services.document_lifecycle import (
    PREVIEW_ASK_DOCUMENT_STATUSES,
    RETRIEVAL_VERSION_CURRENT,
    RETRIEVAL_VERSION_LIVE,
    VISIBLE_ASK_DOCUMENT_STATUSES,
)

router = APIRouter()
admin_router = APIRouter()


def _build_log_detail_response(record) -> KbChatLogDetail:
    return KbChatLogDetail(
        id=record.id,
        user_id=record.user_id,
        session_id=record.session_id,
        product_id=record.product_id,
        project_id=record.project_id,
        project_name=record.project_name,
        project_app_id=record.project_app_id,
        project_app_name=record.project_app_name,
        external_user_id=record.external_user_id,
        external_user_name=record.external_user_name,
        knowledge_base_id=record.knowledge_base_id,
        knowledge_base_name=record.knowledge_base_name,
        category_id=record.category_id,
        category_name=record.category_name,
        query=record.query,
        answer_text=record.answer_text,
        answer_status=record.answer_status,
        retrieval_status=record.retrieval_status,
        retrieved_count=record.retrieved_count,
        latency_ms=record.latency_ms,
        feedback_value=record.feedback_value,
        feedback_note=record.feedback_note,
        suggested_review_label=record.suggested_review_label,
        review_label=record.review_label,
        review_note=record.review_note,
        reviewed_at=record.reviewed_at,
        reviewed_by_user_id=record.reviewed_by_user_id,
        created_at=record.created_at,
        team_id=record.team_id,
        team_name=record.team_name,
        assistant_id=record.assistant_id,
        assistant_name=record.assistant_name,
        retrieval_status_reason=record.retrieval_status_reason,
        retrieval_queries=list(record.retrieval_queries or []),
        retrieval_funnel=(
            KbChatRetrievalFunnel(
                mode=record.retrieval_funnel.get("mode"),
                query_count=int(record.retrieval_funnel.get("query_count") or 0),
                rewritten_queries=[
                    KbChatRetrievalQueryStat(
                        query=str(item.get("query") or ""),
                        chunk_count=int(item.get("chunk_count") or 0),
                    )
                    for item in (record.retrieval_funnel.get("rewritten_queries") or [])
                    if isinstance(item, dict) and str(item.get("query") or "").strip()
                ],
                stages=[
                    KbChatRetrievalFunnelStage(
                        key=str(item.get("key") or ""),
                        label=str(item.get("label") or ""),
                        chunk_count=int(item.get("chunk_count") or 0),
                        note=(
                            str(item.get("note"))
                            if isinstance(item.get("note"), str)
                            else None
                        ),
                    )
                    for item in (record.retrieval_funnel.get("stages") or [])
                    if isinstance(item, dict) and str(item.get("key") or "").strip()
                ],
            )
            if isinstance(record.retrieval_funnel, dict)
            else None
        ),
        answer_context=record.answer_context,
        retrieved_docs=[
            KbChatDiagnosticDoc(
                rank=doc.rank,
                content=doc.content,
                metadata=dict(doc.metadata or {}),
            )
            for doc in record.retrieved_docs
        ],
        conversation_context=[
            KbChatDiagnosticMessage(
                role=message.role,
                content=message.content,
                created_at=message.created_at,
                is_current_turn=message.is_current_turn,
            )
            for message in record.conversation_context
        ],
    )


async def _require_team_scope(
    *,
    request: KbChatRequest,
    db: AsyncSession,
    current_user: User,
) -> None:
    if request.team_id is None:
        raise HTTPException(status_code=400, detail="team_id is required")
    permission_service = PermissionService(db)
    if not await permission_service.can_access_team(current_user, int(request.team_id)):
        raise HTTPException(status_code=403, detail="Team access denied")


async def _require_log_team_permission(
    *,
    db: AsyncSession,
    current_user: User,
    team_id: int | None,
    permission: str,
) -> None:
    if team_id is None:
        if not PermissionService.is_system_admin(current_user):
            raise HTTPException(status_code=403, detail="Log team scope is unavailable")
        return
    if not await PermissionService(db).has_team_permission(current_user, team_id, permission):
        raise HTTPException(status_code=403, detail="QA log permission denied")


@router.get("/teams", response_model=list[TeamResponse])
async def ask_teams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = TeamRepository(db, user_id=current_user.id)
    return await repo.list_user_teams()


@router.get("/sessions", response_model=list[KbChatSessionSummary])
async def ask_sessions(
    limit: int = Query(30, ge=1, le=100, description="Max number of sessions to return"),
    current_user: User = Depends(get_current_user),
):
    return await get_kb_chat_service().list_sessions(user_id=current_user.id, limit=limit)


@router.get("/sessions/{session_id}", response_model=KbChatSessionDetail)
async def ask_session_detail(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    session = await get_kb_chat_service().get_session(
        user_id=current_user.id,
        session_id=session_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_ask_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    deleted = await get_kb_chat_service().delete_session(
        user_id=current_user.id,
        session_id=session_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return None


@router.post("/invoke", response_model=KbChatResponse)
async def ask_invoke(
    request: KbChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_team_scope(request=request, db=db, current_user=current_user)
    try:
        return await get_kb_chat_service().invoke(request, user_id=current_user.id)
    except Exception as exc:
        logger.exception("[Ask] invoke failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stream")
async def ask_stream(
    request: KbChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_team_scope(request=request, db=db, current_user=current_user)
    return StreamingResponse(
        get_kb_chat_service().stream(request, user_id=current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/feedback/{log_id}")
async def submit_ask_feedback(
    log_id: int,
    body: KbChatFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = KbChatLogRepository(db)
    existing = await repo.get_by_id(log_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="KB chat log not found")
    if existing.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot submit feedback for another user")
    await repo.submit_feedback(
        log_id=log_id,
        feedback_value=body.feedback_value,
        feedback_note=body.feedback_note,
    )
    return {"message": "Feedback saved"}


@admin_router.post("/preview", response_model=KbChatResponse)
async def admin_ask_preview(
    request: KbChatPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    await _require_team_scope(request=request, db=db, current_user=current_user)
    allowed_statuses = (
        list(PREVIEW_ASK_DOCUMENT_STATUSES)
        if request.include_unpublished
        else list(VISIBLE_ASK_DOCUMENT_STATUSES)
    )
    runtime_request = SimpleNamespace(
        query=request.query,
        team_id=request.team_id,
        knowledge_base_id=request.knowledge_base_id,
        category_id=request.category_id,
        session_id=request.session_id,
        allowed_document_statuses=allowed_statuses,
        retrieval_version_mode=(
            RETRIEVAL_VERSION_CURRENT
            if request.include_unpublished
            else RETRIEVAL_VERSION_LIVE
        ),
    )
    return await get_kb_chat_service().invoke(runtime_request, user_id=current_user.id)


@admin_router.get("/logs", response_model=KbChatLogListResponse)
async def list_ask_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    team_id: int | None = Query(None),
    project_id: int | None = Query(None),
    project_app_id: int | None = Query(None),
    external_user_id: str | None = Query(None),
    knowledge_base_id: int | None = Query(None),
    category_id: int | None = Query(None),
    answer_status: str | None = Query(None),
    retrieval_status: str | None = Query(None),
    feedback_value: str | None = Query(None),
    query_keyword: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    zero_hits_only: bool = Query(False),
    high_latency_only: bool = Query(False),
    high_latency_threshold_ms: int = Query(5000, ge=1, le=120000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    permission_service = PermissionService(db)
    accessible_team_ids = await permission_service.list_accessible_team_ids(current_user)
    if team_id is not None:
        if not await permission_service.has_team_permission(
            current_user, team_id, PERMISSION_VIEW_QA_LOG
        ):
            raise HTTPException(status_code=403, detail="QA log permission denied")
        scoped_team_ids = None
    else:
        scoped_team_ids = accessible_team_ids

    created_from = datetime.combine(start_date, time.min) if start_date else None
    created_to = datetime.combine(end_date, time.max) if end_date else None
    records, total = await KbChatLogRepository(db).list_logs(
        page=page,
        page_size=page_size,
        team_id=team_id,
        team_ids=scoped_team_ids,
        project_id=project_id,
        project_app_id=project_app_id,
        external_user_id=external_user_id,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        answer_status=answer_status,
        retrieval_status=retrieval_status,
        feedback_value=feedback_value,
        query_keyword=query_keyword,
        created_from=created_from,
        created_to=created_to,
        zero_hits_only=zero_hits_only,
        high_latency_only=high_latency_only,
        high_latency_threshold_ms=high_latency_threshold_ms,
    )
    return KbChatLogListResponse(
        items=[
            KbChatLogItem(
                id=item.id,
                user_id=item.user_id,
                session_id=item.session_id,
                product_id=item.product_id,
                project_id=item.project_id,
                project_name=item.project_name,
                project_app_id=item.project_app_id,
                project_app_name=item.project_app_name,
                external_user_id=item.external_user_id,
                external_user_name=item.external_user_name,
                team_id=item.team_id,
                team_name=item.team_name,
                knowledge_base_id=item.knowledge_base_id,
                knowledge_base_name=item.knowledge_base_name,
                assistant_id=item.assistant_id,
                assistant_name=item.assistant_name,
                category_id=item.category_id,
                category_name=item.category_name,
                query=item.query,
                answer_text=item.answer_text,
                answer_status=item.answer_status,
                retrieval_status=item.retrieval_status,
                retrieved_count=item.retrieved_count,
                latency_ms=item.latency_ms,
                feedback_value=item.feedback_value,
                feedback_note=item.feedback_note,
                suggested_review_label=item.suggested_review_label,
                review_label=item.review_label,
                review_note=item.review_note,
                reviewed_at=item.reviewed_at,
                reviewed_by_user_id=item.reviewed_by_user_id,
                created_at=item.created_at,
            )
            for item in records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.post("/logs/{log_id}/review")
async def review_ask_log(
    log_id: int,
    body: KbChatReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    repo = KbChatLogRepository(db)
    detail = await repo.get_log_detail(log_id=log_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="KB chat log not found")
    await _require_log_team_permission(
        db=db,
        current_user=current_user,
        team_id=detail.team_id,
        permission=PERMISSION_REVIEW_QA_LOG,
    )
    row = await repo.submit_review(
        log_id=log_id,
        review_label=body.review_label,
        review_note=body.review_note,
        reviewer_user_id=current_user.id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="KB chat log not found")
    return {"message": "Review saved"}


@admin_router.get("/logs/{log_id}", response_model=KbChatLogDetail)
async def get_ask_log_detail(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    record = await KbChatLogRepository(db).get_log_detail(log_id=log_id)
    if record is None:
        raise HTTPException(status_code=404, detail="KB chat log not found")
    await _require_log_team_permission(
        db=db,
        current_user=current_user,
        team_id=record.team_id,
        permission=PERMISSION_VIEW_QA_LOG,
    )

    return _build_log_detail_response(record)
