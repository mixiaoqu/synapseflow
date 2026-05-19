"""Query rewrite node for end-user knowledge-base chat."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from loguru import logger

from app.agents.common.retrieval import pick_query_from_state
from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatState
from app.services.kb_query_rewrite import build_kb_chat_retrieval_queries


def _coerce_positive_int(value: Any, *, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _build_runtime_context(state: KbChatState) -> dict[str, Any]:
    page_config = dict(state.get("page_config") or {})
    page_context = dict(state.get("page_context") or {})
    return {
        "page_name": page_config.get("page_name"),
        "page_type": page_context.get("page_type") or page_config.get("page_type"),
        "page_description": page_config.get("page_description"),
    }


async def user_kb_rewrite_query_node(state: KbChatState) -> dict[str, Any]:
    """Rewrite the current query according to the retrieval plan."""

    query = pick_query_from_state(state, "query")
    stream_writer = get_optional_stream_writer()
    retrieval_plan = state.get("retrieval_plan") or {}
    rewrite_plan = retrieval_plan.get("rewrite") or {}
    if retrieval_plan.get("retrieval_required") is False:
        return {
            "retrieval_queries": [],
            "rewrite_meta": {
                "used": False,
                "mode": "skip",
                "query_count": 0,
                "latency_ms": 0,
                "fallback": False,
            },
        }

    rewrite_enabled = bool(rewrite_plan.get("enabled"))
    mode = str(rewrite_plan.get("mode") or "skip").strip().lower()
    max_queries = _coerce_positive_int(rewrite_plan.get("max_queries"), default=1, minimum=1)
    strategies = [
        str(item).strip()
        for item in list(rewrite_plan.get("strategies") or [])
        if str(item or "").strip()
    ]
    emit_progress(
        stream_writer,
        node_id="rewrite_query",
        stage="rewrite",
        message=(
            "正在优化检索问题..."
            if rewrite_enabled and mode != "skip"
            else "正在准备检索问题..."
        ),
        rewrite_mode=(mode if rewrite_enabled else "skip"),
        max_queries=max_queries,
    )
    started_at = perf_counter()
    rewrite_result = await build_kb_chat_retrieval_queries(
        query,
        chat_history=state.get("chat_history") or [],
        memory_summary=state.get("memory_summary"),
        runtime_context=_build_runtime_context(state),
        mode=(mode if rewrite_enabled else "skip"),
        max_queries=max_queries,
        strategies=strategies,
    )
    retrieval_queries = list(rewrite_result.get("queries") or [])
    latency_ms = int((perf_counter() - started_at) * 1000)
    effective_mode = mode if rewrite_enabled else "skip"
    fallback = effective_mode == "llm" and len(retrieval_queries) <= 1
    logger.info(
        "[KB Rewrite] mode={} queries={} latency_ms={} fallback={}",
        effective_mode,
        len(retrieval_queries),
        latency_ms,
        fallback,
    )
    return {
        "retrieval_queries": retrieval_queries,
        "rewrite_meta": {
            "used": rewrite_enabled,
            "mode": effective_mode,
            "query_count": len(retrieval_queries),
            "latency_ms": latency_ms,
            "fallback": fallback,
        },
    }
