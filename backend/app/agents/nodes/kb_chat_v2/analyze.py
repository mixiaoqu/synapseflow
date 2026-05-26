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
        "summary_lookup": {"fast": 2, "standard": 3, "broad": 5},
        "relationship_lookup": {"fast": 2, "standard": 3, "broad": 3},
        "attribute_lookup": {"fast": 1, "standard": 2, "broad": 2},
        "definition_lookup": {"fast": 1, "standard": 1, "broad": 2},
    }
    max_queries = (
        max_queries_matrix.get(question_type, max_queries_matrix["definition_lookup"]).get(
            retrieval_complexity,
            1,
        )
    )
    strategies = ["query_compaction", "terminology_normalization"]
    if question_type == "relationship_lookup":
        strategies.extend(["context_completion", "relationship_focus"])
    elif question_type == "summary_lookup":
        strategies.append("multi_aspect_split")
        if retrieval_complexity == "broad":
            strategies.append("subtopic_expansion")
    elif question_type == "attribute_lookup":
        strategies.append("attribute_focus")
    elif question_type == "definition_lookup":
        strategies.append("definition_focus")
    return {
        "enabled": True,
        "question_type": question_type,
        "retrieval_complexity": retrieval_complexity,
        "max_queries": max_queries,
        "strategies": strategies,
    }


def _build_graph_plan(
    *,
    question_type: str,
    retrieval_strategy: str,
    graph_limit: int,
) -> dict[str, Any]:
    if retrieval_strategy == "skip":
        return {
            "enabled": False,
            "limit": 0,
            "intent": None,
            "graph_mode": None,
            "requires_grounding": False,
            "max_hops": 0,
            "boost": "none",
        }

    if question_type == "relationship_lookup":
        return {
            "enabled": True,
            "limit": graph_limit,
            "intent": "relation_lookup",
            "graph_mode": "relation_evidence",
            "requires_grounding": True,
            "max_hops": 1,
            "boost": "high",
        }

    if question_type == "summary_lookup":
        return {
            "enabled": True,
            "limit": graph_limit,
            "intent": "neighborhood_lookup",
            "graph_mode": "neighborhood_summary",
            "requires_grounding": True,
            "max_hops": 1,
            "boost": "medium",
        }

    if question_type in {"attribute_lookup", "definition_lookup"}:
        return {
            "enabled": True,
            "limit": graph_limit,
            "intent": "entity_summary",
            "graph_mode": "entity_summary",
            "requires_grounding": True,
            "max_hops": 0,
            "boost": "low",
        }

    return {
        "enabled": True,
        "limit": graph_limit,
        "intent": "relation_lookup",
        "graph_mode": "relation_evidence",
        "requires_grounding": True,
        "max_hops": 1,
        "boost": "medium",
    }


def _build_fusion_plan(*, question_type: str, retrieval_strategy: str) -> dict[str, Any]:
    if retrieval_strategy == "skip":
        return {"policy": "none", "graph_boost": "none"}
    if question_type == "relationship_lookup":
        return {"policy": "balanced", "graph_boost": "high"}
    if question_type == "summary_lookup":
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
                "text": {"enabled": False, "recall_k": 0, "lexical_k": 0},
                "graph": graph_plan,
            },
            "rerank": {"enabled": False, "top_k": 0},
            "context": {"final_top_k": 0, "budget_chars": 0, "llm_reference_top_k": 0},
            "fusion": fusion_plan,
        }

    return {
        "retrieval_strategy": "parallel_fusion",
        "channels": {
            "text": {"enabled": True, "recall_k": recall_k, "lexical_k": lexical_k},
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


def build_kb_chat_v2_execution_plan(
    *,
    question_type: str,
    retrieval_strategy: str,
    retrieval_complexity: str,
) -> dict[str, Any]:
    if retrieval_strategy == "skip":
        return {
            "rewrite": {
                "enabled": False,
                "question_type": question_type,
                "retrieval_complexity": retrieval_complexity,
                "max_queries": 0,
                "strategies": [],
            },
            "retrieval_strategy": "skip",
            "channels": {
                "text": {"enabled": False, "recall_k": 0, "lexical_k": 0},
                "graph": _build_graph_plan(
                    question_type=question_type,
                    retrieval_strategy=retrieval_strategy,
                    graph_limit=0,
                ),
            },
            "rerank": {"enabled": False, "top_k": 0},
            "context": {"final_top_k": 0, "budget_chars": 0, "llm_reference_top_k": 0},
            "fusion": _build_fusion_plan(
                question_type=question_type,
                retrieval_strategy=retrieval_strategy,
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
            retrieval_strategy=retrieval_strategy,
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
        retrieval_strategy=route["retrieval_strategy"],
        retrieval_complexity=route["retrieval_complexity"],
    )
    plan_latency_ms = int((perf_counter() - plan_started_at) * 1000)

    result: dict[str, Any] = {
        "question_type": route["question_type"],
        "retrieval_strategy": route["retrieval_strategy"],
        "retrieval_complexity": route["retrieval_complexity"],
        "retrieval_required": route["retrieval_required"],
        "needs_clarification": route["needs_clarification"],
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
                    "graph": {"graph_used": False, "graph_hits": 0, "empty_reason": "skipped"},
                    "final_hits": 0,
                    "empty_reason": "skipped",
                },
                "retrieval_queries": [],
                "retrieved_docs": [],
                "context": "",
            }
        )
    return result
