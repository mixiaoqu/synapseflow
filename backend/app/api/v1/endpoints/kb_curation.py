"""Knowledge-base curation API."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies.auth import get_current_user
from app.application.kb_curation_service import kb_curation_service
from app.db.models import User
from app.models.schemas.qa import QARequest, QAResponse

router = APIRouter()


@router.post("/invoke", response_model=QAResponse)
async def kb_curation_invoke(
    request: QARequest,
    current_user: User = Depends(get_current_user),
):
    """Synchronously run KB curation for the current user."""
    try:
        return await kb_curation_service.invoke(request, user_id=current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stream")
async def kb_curation_stream(
    request: QARequest,
    current_user: User = Depends(get_current_user),
):
    """Stream KB curation output for the current user via SSE."""
    return StreamingResponse(
        kb_curation_service.stream(request, user_id=current_user.id),
        media_type="text/event-stream",
    )
