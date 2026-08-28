"""Administrative Agent preview and QA review APIs."""

from __future__ import annotations

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_review_roles
from app.application.agent.input_builder import AgentRunRequest
from app.application.agent.run_service import get_agent_run_service
from app.application.assistant_service import AssistantService
from app.application.model_usage_service import model_usage_service
from app.application.permission_service import PermissionService
from app.core.authz import PERMISSION_REVIEW_QA_LOG, PERMISSION_VIEW_QA_LOG
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.kb_chat import (
    KbChatDiagnosticMessage,
    KbChatLogDetail,
    KbChatLogItem,
    KbChatLogListResponse,
    KbChatPreviewRequest,
    KbChatResponse,
    KbChatReviewRequest,
)
from app.repositories.kb_chat_log_repository import KbChatLogRepository
from app.services.document_lifecycle import (
    PREVIEW_ASK_DOCUMENT_STATUSES,
    VISIBLE_ASK_DOCUMENT_STATUSES,
)

router = APIRouter()


@router.get("/cost-summary")
async def get_cost_summary(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    team_id: int | None = Query(None),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    permission_service = PermissionService(db)
    accessible_team_ids = await permission_service.list_accessible_team_ids(current_user)
    if team_id is not None:
        if (
            accessible_team_ids is not None
            and team_id not in accessible_team_ids
            and not PermissionService.is_system_admin(current_user)
        ):
            raise HTTPException(status_code=403, detail="Cost center team access denied")
        scoped_team_ids = [team_id]
    else:
        scoped_team_ids = accessible_team_ids
    return await model_usage_service.summary(
        db,
        team_ids=scoped_team_ids,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
    )


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
        latency_ms=record.latency_ms,
        text_hit_count=record.text_hit_count,
        graph_hit_count=record.graph_hit_count,
        merged_candidate_count=record.merged_candidate_count,
        final_context_count=record.final_context_count,
        empty_reason=record.empty_reason,
        rerank_enabled=record.rerank_enabled,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        total_tokens=record.total_tokens,
        estimated_cost=record.estimated_cost,
        token_usage=record.token_usage,
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
        trace_payload=(
            dict(record.trace_payload)
            if isinstance(record.trace_payload, dict)
            else None
        ),
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
    request: KbChatPreviewRequest,
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


async def _build_admin_preview_request(
    request: KbChatPreviewRequest,
    db: AsyncSession,
    current_user: User,
):
    await _require_team_scope(request=request, db=db, current_user=current_user)
    allowed_statuses = (
        list(PREVIEW_ASK_DOCUMENT_STATUSES)
        if request.include_unpublished
        else list(VISIBLE_ASK_DOCUMENT_STATUSES)
    )
    assistant = None
    if request.assistant_id is not None:
        assistant = await AssistantService(
            db,
            user_id=current_user.id,
            user=current_user,
        ).get_profile(request.assistant_id, active_only=True)
        if assistant.team_id != request.team_id:
            raise HTTPException(status_code=400, detail="Assistant does not belong to team scope")
    runtime_request = AgentRunRequest(
        query=request.query,
        team_id=request.team_id,
        knowledge_base_id=request.knowledge_base_id,
        category_id=request.category_id,
        assistant_id=assistant.id if assistant else None,
        assistant_name=assistant.name if assistant else None,
        assistant_llm_model_key=assistant.llm_model_key if assistant else None,
        assistant_persona_prompt=assistant.persona_prompt if assistant else None,
        assistant_rule_template=assistant.rule_template if assistant else None,
        session_id=request.session_id,
        allowed_document_statuses=allowed_statuses,
        source_surface="admin_qa_preview",
    )
    return runtime_request


@router.post("/preview", response_model=KbChatResponse)
async def admin_ask_preview(
    request: KbChatPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    runtime_request = await _build_admin_preview_request(request, db, current_user)
    return await get_agent_run_service().preview(runtime_request, user_id=current_user.id)


@router.post("/preview/stream")
async def admin_ask_preview_stream(
    request: KbChatPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    runtime_request = await _build_admin_preview_request(request, db, current_user)
    stream = get_agent_run_service().stream(
        runtime_request,
        user_id=current_user.id,
        persist=False,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/logs", response_model=KbChatLogListResponse)
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
                latency_ms=item.latency_ms,
                text_hit_count=item.text_hit_count,
                graph_hit_count=item.graph_hit_count,
                merged_candidate_count=item.merged_candidate_count,
                final_context_count=item.final_context_count,
                empty_reason=item.empty_reason,
                rerank_enabled=item.rerank_enabled,
                input_tokens=item.input_tokens,
                output_tokens=item.output_tokens,
                total_tokens=item.total_tokens,
                estimated_cost=item.estimated_cost,
                token_usage=item.token_usage,
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


@router.post("/logs/{log_id}/review")
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


@router.get("/logs/{log_id}", response_model=KbChatLogDetail)
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
