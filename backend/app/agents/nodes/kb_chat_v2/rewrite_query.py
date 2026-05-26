"""Rewrite and entity extraction node for kb_chat_v2."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatV2State
from app.services.kb_query_rewrite import build_kb_chat_retrieval_queries


async def build_kb_chat_v2_rewrite(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None,
    memory_summary: str | None,
    page_context: dict[str, Any] | None,
    rewrite_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    plan = dict(rewrite_plan or {})
    question_type = str(plan.get("question_type") or "entity_lookup").strip().lower()
    retrieval_complexity = str(plan.get("retrieval_complexity") or "standard").strip().lower()
    max_queries = int(plan.get("max_queries") or 1)
    strategies = [str(item) for item in list(plan.get("strategies") or []) if str(item)]

    started_at = perf_counter()
    rewrite_result = await build_kb_chat_retrieval_queries(
        query,
        chat_history=chat_history or [],
        memory_summary=memory_summary,
        runtime_context=page_context or {},
        question_type=question_type,
        retrieval_label=retrieval_complexity,
        max_queries=max_queries,
        strategies=strategies,
    )
    text_queries = list(rewrite_result.get("queries") or [])
    candidate_entities = list(rewrite_result.get("candidate_entities") or [])
    trace = {
        "used": True,
        "engine": "llm",
        "policy": question_type,
        "retrieval_complexity": retrieval_complexity,
        "query_count": len(text_queries),
        "entity_count": len(candidate_entities),
        "fallback_used": False,
        "latency_ms": int((perf_counter() - started_at) * 1000),
    }
    return {
        "text_queries": text_queries,
        "candidate_entities": candidate_entities,
        "rewrite_trace": trace,
        "retrieval_queries": text_queries,
    }


async def kb_chat_v2_rewrite_query_node(state: KbChatV2State) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    if str(state.get("retrieval_strategy") or "").strip().lower() == "skip":
        trace = {"used": False, "engine": "skip", "query_count": 0, "entity_count": 0}
        return {
            "text_queries": [],
            "candidate_entities": [],
            "rewrite_trace": trace,
            "retrieval_queries": [],
        }
    emit_progress(
        stream_writer,
        node_id="rewrite_query",
        stage="rewrite",
        message="正在整理检索线索",
    )
    return await build_kb_chat_v2_rewrite(
        str(state.get("query") or ""),
        chat_history=list(state.get("chat_history") or []),
        memory_summary=state.get("memory_summary"),
        page_context=dict(state.get("page_context") or {}),
        rewrite_plan=((state.get("retrieval_execution_plan") or {}).get("rewrite") or {}),
    )
