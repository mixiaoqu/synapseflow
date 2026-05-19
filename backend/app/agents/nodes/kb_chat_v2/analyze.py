"""Analyze node for kb_chat_v2."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.nodes.kb_chat_v2.route import build_kb_chat_v2_route
from app.agents.states import KbChatV2State
from app.core.config.registry import config_registry


def _build_rewrite_plan(question_type: str, retrieval_complexity: str) -> dict[str, Any]:
    max_queries_matrix = {
        "entity_lookup": {"fast": 1, "standard": 2, "broad": 2},
        "relationship_lookup": {"fast": 2, "standard": 3, "broad": 3},
        "procedural_lookup": {"fast": 2, "standard": 3, "broad": 4},
        "compare_lookup": {"fast": 3, "standard": 4, "broad": 4},
        "summary_lookup": {"fast": 3, "standard": 4, "broad": 5},
        "followup_lookup": {"fast": 1, "standard": 2, "broad": 3},
    }
    max_queries = (
        max_queries_matrix.get(question_type, max_queries_matrix["entity_lookup"]).get(
            retrieval_complexity,
            2,
        )
    )
    strategies = ["query_compaction", "terminology_normalization"]
    if question_type in {"followup_lookup", "relationship_lookup"}:
        strategies.append("context_completion")
    if question_type in {"compare_lookup", "summary_lookup"} and max_queries > 1:
        strategies.append("multi_aspect_split")
    if question_type == "procedural_lookup":
        strategies.append("procedural_focus")
    if question_type == "relationship_lookup":
        strategies.append("relationship_focus")
    if question_type == "summary_lookup" and retrieval_complexity == "broad":
        strategies.append("subtopic_expansion")
    return {
        "enabled": True,
        "question_type": question_type,
        "retrieval_complexity": retrieval_complexity,
        "max_queries": max_queries,
        "strategies": strategies,
    }


def build_kb_chat_v2_execution_plan(
    *,
    question_type: str,
    retrieval_required: bool,
    retrieval_complexity: str,
) -> dict[str, Any]:
    if not retrieval_required:
        return {
            "rewrite": {
                "enabled": False,
                "question_type": question_type,
                "retrieval_complexity": retrieval_complexity,
                "max_queries": 0,
                "strategies": [],
            },
            "channels": {
                "vector": {"enabled": False, "recall_k": 0},
                "lexical": {"enabled": False, "recall_k": 0},
                "graph": {"enabled": False, "limit": 0},
            },
            "rerank": {"enabled": False, "top_k": 0},
            "context": {"final_top_k": 0, "budget_chars": 0, "llm_reference_top_k": 0},
        }

    retrieval_cfg = config_registry.get_rag_config().retrieval
    profile = retrieval_cfg.profiles.get(retrieval_complexity) or retrieval_cfg.profiles["standard"]
    final_top_k = int(profile.final_top_k)
    llm_reference_top_k = (
        int(profile.llm_reference_top_k)
        if profile.llm_reference_top_k is not None
        else final_top_k
    )
    return {
        "rewrite": _build_rewrite_plan(question_type, retrieval_complexity),
        "channels": {
            "vector": {"enabled": True, "recall_k": int(profile.recall_k)},
            "lexical": {"enabled": True, "recall_k": int(profile.lexical_k)},
            "graph": {"enabled": True, "limit": int(profile.graph_limit)},
        },
        "rerank": {"enabled": bool(profile.rerank_enabled), "top_k": final_top_k},
        "context": {
            "final_top_k": final_top_k,
            "budget_chars": int(profile.context_budget),
            "llm_reference_top_k": llm_reference_top_k,
        },
    }


async def kb_chat_v2_analyze_node(
    state: KbChatV2State,
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    emit_progress(
        stream_writer,
        node_id="analyze",
        stage="analyze",
        message="正在分析问题并生成检索方案",
    )
    page_context = dict(state.get("page_context") or {})
    page_config = dict(state.get("page_config") or {})

    route_started_at = perf_counter()
    route = await build_kb_chat_v2_route(
        str(state.get("query") or ""),
        chat_history=list(state.get("chat_history") or []),
        memory_summary=state.get("memory_summary"),
        page_type=page_context.get("page_type") or page_config.get("page_type"),
        llm_factory=llm_factory,
    )
    route_latency_ms = int((perf_counter() - route_started_at) * 1000)

    plan_started_at = perf_counter()
    execution_plan = build_kb_chat_v2_execution_plan(
        question_type=route["question_type"],
        retrieval_required=route["retrieval_required"],
        retrieval_complexity=route["retrieval_complexity"],
    )
    plan_latency_ms = int((perf_counter() - plan_started_at) * 1000)

    result: dict[str, Any] = {
        "question_type": route["question_type"],
        "retrieval_complexity": route["retrieval_complexity"],
        "retrieval_required": route["retrieval_required"],
        "route_reason": route["reason"],
        "route_trace": {"latency_ms": route_latency_ms},
        "retrieval_execution_plan": execution_plan,
        "plan_trace": {"latency_ms": plan_latency_ms},
    }
    if not route["retrieval_required"]:
        result.update(
            {
                "text_queries": [],
                "candidate_entities": [],
                "rewrite_trace": {
                    "used": False,
                    "engine": "skip",
                    "query_count": 0,
                    "entity_count": 0,
                },
                "retrieval_trace": {
                    "text": {"skipped": True, "text_hits": 0},
                    "graph": {
                        "graph_used": False,
                        "graph_hits": 0,
                        "empty_reason": "skipped",
                    },
                    "final_hits": 0,
                    "empty_reason": "skipped",
                },
                "retrieval_queries": [],
                "retrieved_docs": [],
                "context": "",
            }
        )
    return result
