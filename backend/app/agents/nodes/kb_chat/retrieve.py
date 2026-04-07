"""Retrieval node for end-user knowledge-base chat."""

from typing import Any, Dict

from app.agents.common.retrieval import pick_query_from_state
from app.agents.states import KbChatState
from app.services.chat_memory import format_chat_history
from app.services.kb_query_rewrite import build_kb_chat_retrieval_queries
from app.services.kb_retrieval import run_kb_retrieval, run_multi_query_kb_retrieval


async def user_kb_retrieve_node(state: KbChatState) -> Dict[str, Any]:
    """Retrieve context for the current user query."""

    query = pick_query_from_state(state, "query")
    retrieval_queries = await build_kb_chat_retrieval_queries(
        query,
        chat_history=state.get("chat_history") or [],
        memory_summary=state.get("memory_summary"),
    )
    history_text = format_chat_history(state.get("chat_history") or [], max_messages=4)

    if len(retrieval_queries) > 1:
        result = await run_multi_query_kb_retrieval(
            query=query,
            retrieval_queries=retrieval_queries,
            knowledge_base_id=state.get("knowledge_base_id"),
            category_id=state.get("category_id"),
            iteration=0,
            log_prefix="[User KB Retrieval]",
            user_id=state.get("user_id"),
        )
    else:
        result = await run_kb_retrieval(
            query=query,
            knowledge_base_id=state.get("knowledge_base_id"),
            category_id=state.get("category_id"),
            iteration=0,
            log_prefix="[User KB Retrieval]",
            user_id=state.get("user_id"),
        )

    result["retrieval_queries"] = retrieval_queries or [query]
    if history_text:
        result["chat_history"] = state.get("chat_history") or []
    return result
