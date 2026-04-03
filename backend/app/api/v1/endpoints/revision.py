"""文档修订 API。"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.application.revision_service import revision_service
from app.models.schemas.revision import SuggestRevisionRequest, SuggestRevisionResponse

router = APIRouter()


@router.post("/suggest", response_model=SuggestRevisionResponse)
async def suggest_revision(request: SuggestRevisionRequest):
    """执行一次建议驱动的文档修订并返回修订结果。"""
    logger.info(
        "[修订] suggest 文档={} 字 建议={} 字",
        len(request.document),
        len(request.suggestions),
    )
    try:
        return await revision_service.suggest(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
