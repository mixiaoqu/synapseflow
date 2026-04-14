"""Knowledge-base chat API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from app.api.dependencies.auth import get_current_user
from app.application.kb_chat_service import get_kb_chat_service
from app.db.models import User
from app.models.schemas.kb_chat import (
    KbChatRequest,
    KbChatResponse,
    KbChatSessionDetail,
    KbChatSessionSummary,
)

router = APIRouter()


@router.get("/sessions", response_model=list[KbChatSessionSummary])
async def kb_chat_sessions(
    limit: int = Query(30, ge=1, le=100, description="Max number of sessions to return"),
    current_user: User = Depends(get_current_user),
):
    """List persisted KB chat sessions for the current user."""
    return await get_kb_chat_service().list_sessions(user_id=current_user.id, limit=limit)


@router.get("/sessions/{session_id}", response_model=KbChatSessionDetail)
async def kb_chat_session_detail(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return one persisted KB chat session for the current user."""
    session = await get_kb_chat_service().get_session(
        user_id=current_user.id,
        session_id=session_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.delete("/sessions/{session_id}", status_code=204)
async def kb_chat_delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete one persisted KB chat session for the current user."""

    deleted = await get_kb_chat_service().delete_session(
        user_id=current_user.id,
        session_id=session_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return None


@router.post("/invoke", response_model=KbChatResponse)
async def kb_chat_invoke(
    request: KbChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Synchronously answer a KB chat request for the current user."""
    try:
        return await get_kb_chat_service().invoke(request, user_id=current_user.id)
    except Exception as exc:
        logger.exception("[KB chat] invoke failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stream")
async def kb_chat_stream(
    request: KbChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream a KB chat response for the current user via SSE."""
    return StreamingResponse(
        get_kb_chat_service().stream(request, user_id=current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
