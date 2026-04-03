"""Knowledge-base chat API."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from app.api.dependencies.auth import get_current_user
from app.application.kb_chat_service import get_kb_chat_service
from app.db.models import User
from app.models.schemas.kb_chat import KbChatRequest, KbChatResponse

router = APIRouter()


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
