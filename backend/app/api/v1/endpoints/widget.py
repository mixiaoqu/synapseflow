"""AgentChat widget endpoints."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.widget import (
    get_widget_session_context,
    require_widget_service_token,
)
from app.application.widget_chat_service import WidgetChatService, WidgetSessionContext
from app.db.session import get_db
from app.models.schemas.kb_chat import (
    KbChatFeedbackRequest,
    KbChatSessionDetail,
    KbChatSessionSummary,
)
from app.models.schemas.widget import (
    WidgetBootstrapResponse,
    WidgetChatRequest,
    WidgetSessionCreate,
    WidgetSessionResponse,
)

router = APIRouter()


@router.post(
    "/session",
    response_model=WidgetSessionResponse,
    dependencies=[Depends(require_widget_service_token)],
)
async def create_widget_session(
    body: WidgetSessionCreate,
    db: AsyncSession = Depends(get_db),
):
    credential = await WidgetChatService(db).create_credential(body)
    return WidgetSessionResponse(
        token=credential.token,
        expires_in_seconds=credential.expires_in_seconds,
    )


@router.get("/bootstrap", response_model=WidgetBootstrapResponse)
async def bootstrap_widget(
    page_type: str | None = Query(default=None, max_length=120),
    context: WidgetSessionContext = Depends(get_widget_session_context),
    db: AsyncSession = Depends(get_db),
):
    return await WidgetChatService(db).bootstrap(context, page_type)


@router.get("/sessions", response_model=list[KbChatSessionSummary])
async def list_widget_sessions(
    limit: int = Query(default=30, ge=1, le=100),
    context: WidgetSessionContext = Depends(get_widget_session_context),
    db: AsyncSession = Depends(get_db),
):
    return await WidgetChatService(db).list_sessions(context, limit)


@router.get("/sessions/{session_id}", response_model=KbChatSessionDetail)
async def get_widget_session(
    session_id: str,
    context: WidgetSessionContext = Depends(get_widget_session_context),
    db: AsyncSession = Depends(get_db),
):
    return await WidgetChatService(db).get_session(context, session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_widget_session(
    session_id: str,
    context: WidgetSessionContext = Depends(get_widget_session_context),
    db: AsyncSession = Depends(get_db),
):
    await WidgetChatService(db).delete_session(context, session_id)


@router.post("/stream")
async def stream_widget_chat(
    body: WidgetChatRequest,
    context: WidgetSessionContext = Depends(get_widget_session_context),
    db: AsyncSession = Depends(get_db),
):
    stream = await WidgetChatService(db).stream(context, body)
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/feedback/{log_id}")
async def submit_widget_feedback(
    log_id: int,
    body: KbChatFeedbackRequest,
    context: WidgetSessionContext = Depends(get_widget_session_context),
    db: AsyncSession = Depends(get_db),
):
    await WidgetChatService(db).submit_feedback(context, log_id, body)
    return {"message": "Feedback saved"}
