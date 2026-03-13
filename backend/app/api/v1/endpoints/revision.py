"""文档修订API端点"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas.revision import RevisionRequest, RevisionResponse
from app.agents.graphs import create_recursive_revision_graph

router = APIRouter()

revision_agent = create_recursive_revision_graph()


@router.post("/invoke", response_model=RevisionResponse)
async def invoke_revision(request: RevisionRequest):
    """
    同步调用文档修订智能体
    """
    try:
        initial_state = {
            "original_doc": request.document,
            "current_doc": request.document,
            "document_structure": {},
            "missing_items": [],
            "revision_history": [],
            "current_revision": "",
            "validation_result": {},
            "iteration": 0,
            "max_iterations": request.max_iterations,
            "is_complete": False,
            "confidence": 0.0
        }
        
        result = await revision_agent.ainvoke(initial_state)
        
        return RevisionResponse(
            revised_document=result["current_doc"],
            revision_history=result["revision_history"],
            confidence=result["confidence"],
            iterations=result["iteration"]
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_revision(request: RevisionRequest):
    """
    流式调用文档修订智能体
    """
    async def event_generator():
        try:
            initial_state = {
                "original_doc": request.document,
                "current_doc": request.document,
                "document_structure": {},
                "missing_items": [],
                "revision_history": [],
                "current_revision": "",
                "validation_result": {},
                "iteration": 0,
                "max_iterations": request.max_iterations,
                "is_complete": False,
                "confidence": 0.0
            }
            
            async for chunk in revision_agent.astream(initial_state):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"
        
        except Exception as e:
            error_msg = {"error": str(e)}
            yield f"data: {json.dumps(error_msg)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
