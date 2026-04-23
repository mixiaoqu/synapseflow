"""Retrieval node for end-user knowledge-base chat."""

from typing import Any, Dict

from loguru import logger

from app.agents.common.retrieval import pick_query_from_state
from app.agents.states import KbChatState
from app.services.chat_memory import format_chat_history
from app.services.kb_query_rewrite import build_kb_chat_retrieval_queries
from app.services.kb_retrieval import run_kb_retrieval, run_multi_query_kb_retrieval


def _coerce_positive_int(value: Any, *, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


async def user_kb_retrieve_node(state: KbChatState) -> Dict[str, Any]:
    """Retrieve context for the current user query."""

    query = pick_query_from_state(state, "query")
    adaptive_policy = state.get("adaptive_policy") or {}
    if adaptive_policy.get("retrieval_required") is False:
        logger.info(
            "[知识库检索] 已按策略跳过检索：类型={}，复杂度={}，原因={}",
            adaptive_policy.get("intent"),
            adaptive_policy.get("complexity"),
            adaptive_policy.get("reason"),
        )
        return {
            "retrieved_docs": [],
            "context": "",
            "kb_retrieval_status": "skipped",
            "retrieval_queries": [],
            "retrieval_funnel": {
                "mode": "skipped",
                "query_count": 0,
                "rewritten_queries": [],
                "stages": [],
            },
        }

    max_queries = _coerce_positive_int(
        adaptive_policy.get("max_queries"),
        default=2,
        minimum=1,
    )
    result_limit = _coerce_positive_int(
        adaptive_policy.get("result_limit"),
        default=8,
        minimum=1,
    )
    context_budget = _coerce_positive_int(
        adaptive_policy.get("context_budget"),
        default=10000,
        minimum=1,
    )
    retrieval_queries = await build_kb_chat_retrieval_queries(
        query,
        chat_history=state.get("chat_history") or [],
        memory_summary=state.get("memory_summary"),
        max_queries=max_queries,
    )
    history_text = format_chat_history(state.get("chat_history") or [], max_messages=4)

    if len(retrieval_queries) > 1:
        result = await run_multi_query_kb_retrieval(
            query=query,
            retrieval_queries=retrieval_queries,
            team_id=state.get("team_id"),
            knowledge_base_id=state.get("knowledge_base_id"),
            category_id=state.get("category_id"),
            iteration=0,
            log_prefix="[User KB Retrieval]",
            user_id=state.get("user_id"),
            result_limit=result_limit,
            context_budget=context_budget,
            document_statuses=state.get("allowed_document_statuses"),
            retrieval_version_mode=state.get("retrieval_version_mode"),
        )
    else:
        result = await run_kb_retrieval(
            query=query,
            team_id=state.get("team_id"),
            knowledge_base_id=state.get("knowledge_base_id"),
            category_id=state.get("category_id"),
            iteration=0,
            log_prefix="[User KB Retrieval]",
            user_id=state.get("user_id"),
            result_limit=result_limit,
            context_budget=context_budget,
            document_statuses=state.get("allowed_document_statuses"),
            retrieval_version_mode=state.get("retrieval_version_mode"),
        )

    result["retrieval_queries"] = retrieval_queries or [query]
    if history_text:
        result["chat_history"] = state.get("chat_history") or []
    return result
