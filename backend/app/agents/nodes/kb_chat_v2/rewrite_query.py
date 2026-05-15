"""Rewrite and entity extraction node for kb_chat_v2."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatV2State
from app.services.kb_query_rewrite import build_kb_chat_retrieval_queries


def _get_rewrite_policy(question_type: str | None, retrieval_label: str | None) -> dict[str, Any]:
    normalized_type = str(question_type or "entity_lookup").strip().lower()
    normalized_label = str(retrieval_label or "standard").strip().lower()

    max_queries_matrix = {
        "entity_lookup": {"fast": 1, "standard": 2, "broad": 2},
        "relationship_lookup": {"fast": 2, "standard": 3, "broad": 3},
        "procedural_lookup": {"fast": 2, "standard": 3, "broad": 4},
        "compare_lookup": {"fast": 3, "standard": 4, "broad": 4},
        "summary_lookup": {"fast": 3, "standard": 4, "broad": 5},
        "followup_lookup": {"fast": 1, "standard": 2, "broad": 3},
        "chitchat": {"fast": 1, "standard": 1, "broad": 1},
        "out_of_scope": {"fast": 1, "standard": 1, "broad": 1},
    }
    max_queries = (
        max_queries_matrix.get(normalized_type, max_queries_matrix["entity_lookup"]).get(
            normalized_label,
            2,
        )
    )
    policy = {
        "policy": normalized_type,
        "retrieval_label": normalized_label,
        "max_queries": max_queries,
        "strategies": ["query_compaction", "terminology_normalization"],
    }

    if normalized_type == "followup_lookup":
        policy["strategies"].append("context_completion")
    if normalized_type in {"compare_lookup", "summary_lookup"} and max_queries > 1:
        policy["strategies"].append("multi_aspect_split")
    if normalized_type == "procedural_lookup":
        policy["strategies"].append("procedural_focus")
    if normalized_type == "relationship_lookup":
        policy["strategies"].append("relationship_focus")
    if normalized_type == "summary_lookup" and normalized_label == "broad":
        policy["strategies"].append("subtopic_expansion")
    if (
        normalized_type in {"followup_lookup", "relationship_lookup"}
        and "context_completion" not in policy["strategies"]
    ):
        policy["strategies"].append("context_completion")
    return policy


async def build_kb_chat_v2_rewrite(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None,
    memory_summary: str | None,
    page_context: dict[str, Any] | None,
    question_type: str | None,
    retrieval_label: str | None,
) -> dict[str, Any]:
    policy = _get_rewrite_policy(question_type, retrieval_label)
    started_at = perf_counter()
    rewrite_result = await build_kb_chat_retrieval_queries(
        query,
        chat_history=chat_history or [],
        memory_summary=memory_summary,
        runtime_context=page_context or {},
        question_type=policy["policy"],
        retrieval_label=policy["retrieval_label"],
        max_queries=policy["max_queries"],
        strategies=policy["strategies"],
    )
    text_queries = list(rewrite_result.get("queries") or [])
    candidate_entities = list(rewrite_result.get("candidate_entities") or [])
    trace = {
        "used": True,
        "engine": "llm",
        "policy": policy["policy"],
        "retrieval_label": policy["retrieval_label"],
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
    if state.get("retrieval_required") is False:
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
        question_type=state.get("question_type"),
        retrieval_label=state.get("retrieval_label"),
    )
