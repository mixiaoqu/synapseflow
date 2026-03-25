"""知识库单轮问答 API（面向最终用户，节点见 agents/nodes/kb_user_qa）"""
import json
import asyncio
from typing import Any, AsyncGenerator, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from app.agents.graphs.kb_simple_qa_graph import create_kb_simple_qa_graph
from app.agents.nodes.kb_user_qa import (
    user_kb_retrieve_node,
    build_user_kb_answer_prompt,
)
from app.models.schemas.kb_qa import KbSimpleQARequest, KbSimpleQAResponse
from app.core.llm import get_llm_for_generation

router = APIRouter()

kb_simple_agent = create_kb_simple_qa_graph()

SSE_EVENT = "message"


def _initial_state(req: KbSimpleQARequest) -> Dict[str, Any]:
    return {
        "messages": [],
        "query": req.query,
        "collection_id": req.collection_id,
        "retrieved_docs": [],
        "context": "",
        "answer": "",
    }


def _stream_chunk_text(chunk: Any) -> str:
    c = getattr(chunk, "content", None)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for x in c:
            if isinstance(x, str):
                parts.append(x)
            elif isinstance(x, dict) and x.get("type") == "text":
                parts.append(str(x.get("text", "")))
        return "".join(parts)
    return ""


def _envelope(typ: str, data: Dict[str, Any]) -> str:
    body = {"type": typ, "data": data}
    return "event: %s\ndata: %s\n\n" % (SSE_EVENT, json.dumps(body, ensure_ascii=False))


@router.post("/invoke", response_model=KbSimpleQAResponse)
async def kb_simple_invoke(request: KbSimpleQARequest):
    """同步：用户检索 + 用户向回答，无迭代评估。"""
    try:
        result = await kb_simple_agent.ainvoke(_initial_state(request))
        return KbSimpleQAResponse(
            answer=result.get("answer", ""),
            retrieved_docs=result.get("retrieved_docs", []),
            session_id=request.session_id,
        )
    except Exception as e:
        logger.exception("[用户知识库问答] invoke 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _stream_events(req: KbSimpleQARequest) -> AsyncGenerator[str, None]:
    state = _initial_state(req)
    try:
        retrieve_out = await user_kb_retrieve_node(state)
        state.update(retrieve_out)
        yield _envelope(
            "retrieved",
            {"retrieved_docs": state.get("retrieved_docs", [])},
        )
        await asyncio.sleep(0)

        prompt = build_user_kb_answer_prompt(
            state.get("query", ""),
            state.get("context", ""),
        )
        llm = get_llm_for_generation()
        full_answer: list[str] = []
        async for chunk in llm.astream(prompt):
            text = _stream_chunk_text(chunk)
            if text:
                full_answer.append(text)
                yield _envelope("token", {"text": text})
        await asyncio.sleep(0)

        yield _envelope(
            "done",
            {"answer": "".join(full_answer)},
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("[用户知识库问答] stream 失败: %s", e)
        yield _envelope("error", {"message": str(e)})


@router.post("/stream")
async def kb_simple_stream(request: KbSimpleQARequest):
    """流式：先检索结果，再 token 流式输出（提示与 invoke 一致）。"""
    return StreamingResponse(
        _stream_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
