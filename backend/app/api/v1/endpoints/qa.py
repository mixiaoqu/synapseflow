"""问答API端点"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas.qa import QARequest, QAResponse
from app.agents.graphs import create_iterative_qa_graph
router = APIRouter()

qa_agent = create_iterative_qa_graph()


@router.post("/invoke", response_model=QAResponse)
async def invoke_qa(request: QARequest):
    """
    同步调用问答智能体
    """
    try:
        initial_state = {
            "messages": [],
            "query": request.query,
            "optimized_query": "",
            "retrieved_docs": [],
            "context": "",
            "answer": "",
            "confidence_score": 0.0,
            "iteration": 0,
            "max_iterations": request.max_iterations,
            "should_continue": True,
            "iteration_history": [],
            "last_evaluation_feedback": None,
            "document_issues": [],
            "collection_id": request.collection_id,
        }

        result = await qa_agent.ainvoke(initial_state)

        return QAResponse(
            answer=result["answer"],
            confidence_score=result["confidence_score"],
            iteration=result["iteration"],
            retrieved_docs=result.get("retrieved_docs", []),
            iteration_history=result.get("iteration_history", []),
            document_issues=result.get("document_issues", []),
            session_id=request.session_id,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_qa(request: QARequest):
    """
    流式调用问答智能体（SSE）
    """
    async def event_generator():
        try:
            initial_state = {
                "messages": [],
                "query": request.query,
                "optimized_query": "",
                "retrieved_docs": [],
                "context": "",
                "answer": "",
                "confidence_score": 0.0,
                "iteration": 0,
                "max_iterations": request.max_iterations,
                "should_continue": True,
                "iteration_history": [],
                "last_evaluation_feedback": None,
                "document_issues": [],
                "collection_id": request.collection_id,
            }
            
            async for chunk in qa_agent.astream(initial_state):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"
        
        except Exception as e:
            error_msg = {"error": str(e)}
            yield f"data: {json.dumps(error_msg)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
