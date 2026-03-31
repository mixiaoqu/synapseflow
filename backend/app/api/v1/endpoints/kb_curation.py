"""面向管理员的知识库治理 API。"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.application import kb_curation_service
from app.models.schemas.qa import QARequest, QAResponse

router = APIRouter()


@router.post("/invoke", response_model=QAResponse)
async def kb_curation_invoke(request: QARequest):
    """同步执行知识库治理问答。"""
    try:
        return await kb_curation_service.invoke(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stream")
async def kb_curation_stream(request: QARequest):
    """以 SSE 方式流式执行知识库治理问答。"""
    return StreamingResponse(
        kb_curation_service.stream(request),
        media_type="text/event-stream",
    )
