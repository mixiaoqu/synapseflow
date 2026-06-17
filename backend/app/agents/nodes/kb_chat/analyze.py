"""Analyze node for knowledge-base chat."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.nodes.kb_chat.route import build_kb_chat_route
from app.agents.states import KbChatState
from app.core.config.registry import config_registry

RETRIEVAL_STRATEGIES = {
    "text_only",
    "graph_only",
    "text_then_graph",
    "graph_then_text",
    "parallel_fusion",
}
TEXT_FIRST_QUESTION_TYPES = {
    "definition_lookup",
    "attribute_lookup",
    "location_lookup",
}
GRAPH_FIRST_QUESTION_TYPES = {
    "relationship_lookup",
    "dependency_lookup",
    "call_chain_lookup",
}
PARALLEL_QUESTION_TYPES = {
    "summary_lookup",
    "flow_lookup",
}


def _build_rewrite_plan(question_type: str, retrieval_complexity: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "question_type": question_type,
        "retrieval_complexity": retrieval_complexity,
    }


def _select_retrieval_strategy(question_type: str, requested_strategy: str) -> str:
    normalized_requested = str(requested_strategy or "").strip().lower()
    if normalized_requested == "skip":
        return "skip"
    if normalized_requested in RETRIEVAL_STRATEGIES and normalized_requested != "parallel_fusion":
        return normalized_requested

    normalized_question_type = str(question_type or "").strip().lower()
    if normalized_question_type in TEXT_FIRST_QUESTION_TYPES:
        return "text_then_graph"
    if normalized_question_type in GRAPH_FIRST_QUESTION_TYPES:
        return "graph_then_text"
    if normalized_question_type in PARALLEL_QUESTION_TYPES:
        return "parallel_fusion"
    return "parallel_fusion"


def _strategy_channels(strategy: str) -> tuple[bool, bool]:
    if strategy == "text_only":
        return True, False
    if strategy == "graph_only":
        return False, True
    if strategy in {"text_then_graph", "graph_then_text", "parallel_fusion"}:
        return True, True
    return False, False


def _build_graph_plan(
    *,
    question_type: str,
    retrieval_strategy: str,
    graph_limit: int,
) -> dict[str, Any]:
    _text_enabled, graph_enabled = _strategy_channels(retrieval_strategy)
    if retrieval_strategy == "skip" or not graph_enabled:
        return {
            "enabled": False,
            "limit": 0,
            "intent": None,
            "graph_mode": None,
            "max_hops": 0,
            "boost": "none",
        }

    if question_type == "relationship_lookup":
        return {
            "enabled": True,
            "limit": graph_limit,
            "intent": "relation_lookup",
            "graph_mode": "relation_evidence",
            "max_hops": 1,
            "boost": "high",
        }

    if question_type in {"dependency_lookup", "call_chain_lookup"}:
        return {
            "enabled": True,
            "limit": graph_limit,
            "intent": "relation_lookup",
            "graph_mode": "relation_evidence",
            "max_hops": 3,
            "boost": "high",
        }

    if question_type == "summary_lookup":
        return {
            "enabled": True,
            "limit": graph_limit,
            "intent": "neighborhood_lookup",
            "graph_mode": "neighborhood_summary",
            "max_hops": 1,
            "boost": "medium",
        }

    if question_type in {"attribute_lookup", "definition_lookup"}:
        return {
            "enabled": True,
            "limit": graph_limit,
            "intent": "entity_summary",
            "graph_mode": "entity_summary",
            "max_hops": 0,
            "boost": "low",
        }

    return {
        "enabled": True,
        "limit": graph_limit,
        "intent": "relation_lookup",
        "graph_mode": "relation_evidence",
        "max_hops": 1,
        "boost": "medium",
    }


def _build_fusion_plan(*, question_type: str, retrieval_strategy: str) -> dict[str, Any]:
    if retrieval_strategy == "skip":
        return {"policy": "none", "graph_boost": "none"}
    if retrieval_strategy == "text_only":
        return {"policy": "text_only", "graph_boost": "none"}
    if retrieval_strategy == "graph_only":
        return {"policy": "graph_only", "graph_boost": "high"}
    if question_type in GRAPH_FIRST_QUESTION_TYPES:
        return {"policy": "balanced", "graph_boost": "high"}
    if question_type in PARALLEL_QUESTION_TYPES:
        return {"policy": "text_primary", "graph_boost": "medium"}
    return {"policy": "text_primary", "graph_boost": "low"}


def _build_retrieval_plan(
    *,
    question_type: str,
    retrieval_strategy: str,
    retrieval_complexity: str,
    final_top_k: int,
    llm_reference_top_k: int,
    recall_k: int,
    lexical_k: int,
    graph_limit: int,
    context_budget: int,
    rerank_enabled: bool,
) -> dict[str, Any]:
    text_enabled, graph_enabled = _strategy_channels(retrieval_strategy)
    graph_plan = _build_graph_plan(
        question_type=question_type,
        retrieval_strategy=retrieval_strategy,
        graph_limit=graph_limit,
    )
    fusion_plan = _build_fusion_plan(
        question_type=question_type,
        retrieval_strategy=retrieval_strategy,
    )
    if retrieval_strategy == "skip":
        return {
            "retrieval_strategy": "skip",
            "channels": {
                "vector": {"enabled": False, "recall_k": 0},
                "lexical": {"enabled": False, "lexical_k": 0},
                "graph": graph_plan,
            },
            "rerank": {"enabled": False, "top_k": 0},
            "context": {"final_top_k": 0, "budget_chars": 0, "llm_reference_top_k": 0},
            "fusion": fusion_plan,
        }

    return {
        "strategy": retrieval_strategy,
        "retrieval_strategy": retrieval_strategy,
        "text_enabled": text_enabled,
        "graph_enabled": graph_enabled,
        "rerank_enabled": rerank_enabled,
        "top_k": final_top_k,
        "channels": {
            "vector": {"enabled": text_enabled, "recall_k": recall_k if text_enabled else 0},
            "lexical": {"enabled": text_enabled, "lexical_k": lexical_k if text_enabled else 0},
            "graph": graph_plan,
        },
        "rerank": {"enabled": rerank_enabled, "top_k": final_top_k},
        "context": {
            "final_top_k": final_top_k,
            "budget_chars": context_budget,
            "llm_reference_top_k": llm_reference_top_k,
        },
        "retrieval_complexity": retrieval_complexity,
        "fusion": fusion_plan,
    }


def build_kb_chat_execution_plan(
    *,
    question_type: str,
    retrieval_strategy: str,
    retrieval_complexity: str,
) -> dict[str, Any]:
    selected_strategy = _select_retrieval_strategy(question_type, retrieval_strategy)
    if selected_strategy == "skip":
        return {
            "rewrite": {
                "enabled": False,
                "question_type": question_type,
                "retrieval_complexity": retrieval_complexity,
            },
            "strategy": "skip",
            "retrieval_strategy": "skip",
            "text_enabled": False,
            "graph_enabled": False,
            "rerank_enabled": False,
            "top_k": 0,
            "channels": {
                "vector": {"enabled": False, "recall_k": 0},
                "lexical": {"enabled": False, "lexical_k": 0},
                "graph": _build_graph_plan(
                    question_type=question_type,
                    retrieval_strategy=selected_strategy,
                    graph_limit=0,
                ),
            },
            "rerank": {"enabled": False, "top_k": 0},
            "context": {"final_top_k": 0, "budget_chars": 0, "llm_reference_top_k": 0},
            "fusion": _build_fusion_plan(
                question_type=question_type,
                retrieval_strategy=selected_strategy,
            ),
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
        **_build_retrieval_plan(
            question_type=question_type,
            retrieval_strategy=selected_strategy,
            retrieval_complexity=retrieval_complexity,
            final_top_k=final_top_k,
            llm_reference_top_k=llm_reference_top_k,
            recall_k=int(profile.recall_k),
            lexical_k=int(profile.lexical_k),
            graph_limit=int(profile.graph_limit),
            context_budget=int(profile.context_budget),
            rerank_enabled=bool(profile.rerank_enabled),
        ),
    }


async def kb_chat_analyze_node(
    state: KbChatState,
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
    route = await build_kb_chat_route(
        str(state.get("query") or ""),
        chat_history=list(state.get("chat_history") or []),
        memory_summary=state.get("memory_summary"),
        page_type=page_context.get("page_type") or page_config.get("page_type"),
        llm_factory=llm_factory,
    )
    route_latency_ms = int((perf_counter() - route_started_at) * 1000)

    plan_started_at = perf_counter()
    execution_plan = build_kb_chat_execution_plan(
        question_type=route["question_type"],
        retrieval_strategy=route["retrieval_strategy"],
        retrieval_complexity=route["retrieval_complexity"],
    )
    plan_latency_ms = int((perf_counter() - plan_started_at) * 1000)

    result: dict[str, Any] = {
        "question_type": route["question_type"],
        "retrieval_strategy": execution_plan["retrieval_strategy"],
        "retrieval_complexity": route["retrieval_complexity"],
        "retrieval_required": route["retrieval_required"],
        "needs_clarification": route["needs_clarification"],
        "candidate_entities": list(route.get("entities") or []),
        "question_intent": {
            "question_type": route["question_type"],
            "entities": list(route.get("entities") or []),
            "needs_path": bool(route.get("needs_path")),
            "needs_relation": bool(route.get("needs_relation")),
            "needs_summary": bool(route.get("needs_summary")),
        },
        "route_reason": route["reason"],
        "route_trace": {"latency_ms": route_latency_ms},
        "retrieval_execution_plan": execution_plan,
        "plan_trace": {"latency_ms": plan_latency_ms},
        "graph_enabled": bool((((execution_plan.get("channels") or {}).get("graph") or {}).get("enabled"))),
        "graph_intent": (((execution_plan.get("channels") or {}).get("graph") or {}).get("intent")),
        "graph_mode": (((execution_plan.get("channels") or {}).get("graph") or {}).get("graph_mode")),
        "graph_requires_grounding": bool(
            (((execution_plan.get("channels") or {}).get("graph") or {}).get("requires_grounding"))
        ),
        "graph_max_hops": int(
            (((execution_plan.get("channels") or {}).get("graph") or {}).get("max_hops") or 0)
        ),
        "graph_budget": int((((execution_plan.get("channels") or {}).get("graph") or {}).get("limit") or 0)),
        "fusion_policy": (((execution_plan.get("fusion") or {}).get("policy"))),
        "graph_boost": (((execution_plan.get("fusion") or {}).get("graph_boost"))),
    }
    if not route["retrieval_required"]:
        result.update(
            {
                "candidate_entities": [],
                "rewrite_trace": {
                    "used": False,
                    "engine": "skip",
                    "query_count": 0,
                    "entity_count": 0,
                },
                "retrieval_trace": {
                    "text": {"skipped": True, "text_hits": 0},
                    "graph": {"graph_used": False, "graph_hits": 0, "empty_reason": "skipped"},
                    "final_hits": 0,
                    "empty_reason": "skipped",
                },
                "semantic_queries": [],
                "lexical_terms": [],
                "candidate_entities": [],
                "retrieved_docs": [],
                "context": "",
            }
        )
    return result
