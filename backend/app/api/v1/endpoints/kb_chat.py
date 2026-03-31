"""面向普通用户的知识库问答 API。"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from app.application import kb_chat_service
from app.models.schemas.kb_chat import KbChatRequest, KbChatResponse

router = APIRouter()


@router.post("/invoke", response_model=KbChatResponse)
async def kb_chat_invoke(request: KbChatRequest):
    """同步执行知识库问答。"""
    try:
        return await kb_chat_service.invoke(request)
    except Exception as exc:
        logger.exception("[知识库问答] invoke 失败: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stream")
async def kb_chat_stream(request: KbChatRequest):
    """以 SSE 方式流式返回知识库问答结果。"""
    return StreamingResponse(
        kb_chat_service.stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
