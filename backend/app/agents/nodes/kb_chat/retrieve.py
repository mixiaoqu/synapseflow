"""Retrieval node for end-user knowledge-base chat."""

from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from app.agents.common.retrieval import pick_query_from_state
from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatState
from app.services.chat_memory import format_chat_history
from app.services.kb_retrieval import run_kb_retrieval, run_multi_query_kb_retrieval

MIN_CONTEXT_CHUNKS = 8


def _coerce_positive_int(value: Any, *, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


async def user_kb_retrieve_node(state: KbChatState) -> Dict[str, Any]:
    """Retrieve context for the current user query."""

    query = pick_query_from_state(state, "query")
    stream_writer = get_optional_stream_writer()
    retrieval_plan = state.get("retrieval_plan") or {}
    retrieval_cfg = retrieval_plan.get("retrieval") or {}
    if retrieval_plan.get("retrieval_required") is False:
        logger.info(
            "[KB Retrieval] skipped by retrieval_plan plan={} reason={}",
            retrieval_plan.get("plan_name"),
            retrieval_plan.get("reason"),
        )
        return {
            "retrieved_docs": [],
            "context": "",
            "kb_retrieval_status": "skipped",
            "retrieval_funnel": {
                "mode": "skipped",
                "query_count": 0,
                "rewritten_queries": [],
                "stages": [],
            },
        }

    retrieval_mode = str(retrieval_cfg.get("mode") or "vector").strip().lower()
    recall_k = _coerce_positive_int(retrieval_cfg.get("recall_k"), default=10, minimum=1)
    lexical_k = _coerce_positive_int(retrieval_cfg.get("lexical_k"), default=0, minimum=0)
    final_top_k = _coerce_positive_int(retrieval_cfg.get("final_top_k"), default=6, minimum=1)
    llm_reference_top_k = _coerce_positive_int(
        retrieval_cfg.get("llm_reference_top_k"),
        default=MIN_CONTEXT_CHUNKS,
        minimum=MIN_CONTEXT_CHUNKS,
    )
    context_budget = _coerce_positive_int(
        retrieval_cfg.get("context_budget"),
        default=8000,
        minimum=1,
    )
    rerank_enabled = bool(retrieval_cfg.get("rerank_enabled"))
    retrieval_queries = [
        str(item).strip()
        for item in list(state.get("retrieval_queries") or [])
        if str(item or "").strip()
    ]
    if not retrieval_queries:
        retrieval_queries = [query]

    history_text = format_chat_history(state.get("chat_history") or [], max_messages=4)

    def emit_retrieval_progress(data: dict[str, Any]) -> None:
        emit_progress(
            stream_writer,
            node_id="retrieve",
            stage=str(data.get("stage") or "retrieve"),
            message=str(data.get("message") or "正在检索知识库..."),
            **{key: value for key, value in data.items() if key not in {"stage", "message"}},
        )

    emit_progress(
        stream_writer,
        node_id="retrieve",
        stage="retrieve",
        message="正在检索知识库...",
        retrieval_mode=retrieval_mode,
        query_count=len(retrieval_queries),
        recall_k=recall_k,
        lexical_k=lexical_k,
    )

    common_kwargs = {
        "team_id": state.get("team_id"),
        "knowledge_base_id": state.get("knowledge_base_id"),
        "knowledge_base_branch_ids": list(state.get("knowledge_base_branch_ids") or []),
        "category_id": state.get("category_id"),
        "log_prefix": "[User KB Retrieval]",
        "user_id": state.get("user_id"),
        "result_limit": final_top_k,
        "llm_reference_top_k": llm_reference_top_k,
        "context_budget": context_budget,
        "document_statuses": state.get("allowed_document_statuses"),
        "retrieval_version_mode": state.get("retrieval_version_mode"),
        "retrieval_mode": retrieval_mode,
        "recall_k": recall_k,
        "lexical_k": lexical_k,
        "rerank_enabled": rerank_enabled,
        "progress_callback": emit_retrieval_progress,
    }
    if len(retrieval_queries) > 1:
        result = await run_multi_query_kb_retrieval(
            query=query,
            retrieval_queries=retrieval_queries,
            **common_kwargs,
        )
    else:
        result = await run_kb_retrieval(
            query=retrieval_queries[0],
            **common_kwargs,
        )

    result["retrieval_queries"] = retrieval_queries
    if history_text:
        result["chat_history"] = state.get("chat_history") or []
    return result
