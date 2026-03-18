"""文档修订API端点（用户建议驱动）"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.models.schemas.revision import SuggestRevisionRequest, SuggestRevisionResponse
from app.agents.graphs import create_suggest_revision_graph

router = APIRouter()
suggest_revision_agent = create_suggest_revision_graph()


@router.post("/suggest", response_model=SuggestRevisionResponse)
async def suggest_revision(request: SuggestRevisionRequest):
    """
    用户建议驱动修订：一次性执行完整流程，返回修订后文档。
    前端展示 Diff 对比，用户确认后选择是否保存到知识库。
    """
    logger.info("[修订] ========== 开始执行文档修订流程 ==========")
    logger.info("[修订] 文档长度: {} 字, 建议长度: {} 字", len(request.document), len(request.suggestions))
    try:
        initial_state = {
            "original_doc": request.document,
            "current_doc": request.document,
            "user_suggestions": request.suggestions,
            "parsed_tasks": [],
            "doc_structure": [],
            "chunks_meta": [],
            "chunks_positions": [],
            "affected_chunk_indices": [],
            "section_hints": {},
            "revised_document": "",
            "doc_id": request.doc_id,
        }
        result = await suggest_revision_agent.ainvoke(initial_state)
        return SuggestRevisionResponse(
            revised_document=result.get("revised_document", result.get("current_doc", "")),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
