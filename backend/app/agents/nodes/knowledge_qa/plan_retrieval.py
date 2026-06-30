"""Retrieval planning helpers for the knowledge_qa workflow."""

from __future__ import annotations

from typing import Any

from app.core.config.registry import config_registry

RETRIEVAL_STRATEGIES = {
    "text_only",
    "graph_only",
    "text_then_graph",
    "graph_then_text",
    "parallel_fusion",
}
GRAPH_FIRST_QUESTION_TYPES = {
    "relationship_lookup",
    "dependency_lookup",
    "call_chain_lookup",
}
PARALLEL_QUESTION_TYPES = {
    "summary_lookup",
    "flow_lookup",
    "location_lookup",
    "attribute_lookup",
}
TEXT_ONLY_QUESTION_TYPES = {
    "definition_lookup",
}


def _build_rewrite_plan(question_type: str, retrieval_complexity: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "question_type": question_type,
        "retrieval_complexity": retrieval_complexity,
    }


def _select_retrieval_strategy(question_type: str, requested_strategy: str) -> str:
    normalized_requested = str(requested_strategy or "").strip().lower()
    if normalized_requested in RETRIEVAL_STRATEGIES and normalized_requested != "parallel_fusion":
        return normalized_requested

    normalized_question_type = str(question_type or "").strip().lower()
    if normalized_question_type in GRAPH_FIRST_QUESTION_TYPES:
        return "graph_then_text"
    if normalized_question_type in PARALLEL_QUESTION_TYPES:
        return "parallel_fusion"
    if normalized_question_type in TEXT_ONLY_QUESTION_TYPES:
        return "text_only"
    return "text_only"


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
    if not graph_enabled:
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
            "graph_mode": "relation_evidence",
            "max_hops": 1,
            "boost": "medium",
        }

    if question_type in {"flow_lookup", "location_lookup", "attribute_lookup"}:
        return {
            "enabled": True,
            "limit": graph_limit,
            "intent": "relation_lookup",
            "graph_mode": "relation_evidence",
            "max_hops": 1,
            "boost": "medium",
        }

    return {
        "enabled": False,
        "limit": 0,
        "intent": None,
        "graph_mode": None,
        "max_hops": 0,
        "boost": "none",
    }


def _build_fusion_plan(*, question_type: str, retrieval_strategy: str) -> dict[str, Any]:
    if retrieval_strategy == "text_only":
        return {"policy": "text_only", "graph_boost": "none"}
    if retrieval_strategy == "graph_only":
        return {"policy": "graph_only", "graph_boost": "high"}
    if question_type in GRAPH_FIRST_QUESTION_TYPES:
        return {"policy": "balanced", "graph_boost": "high"}
    if question_type in PARALLEL_QUESTION_TYPES:
        return {"policy": "text_primary", "graph_boost": "medium"}
    return {"policy": "text_primary", "graph_boost": "low"}


def build_knowledge_qa_retrieval_plan(
    *,
    question_type: str,
    retrieval_strategy: str,
    retrieval_complexity: str,
) -> dict[str, Any]:
    selected_strategy = _select_retrieval_strategy(question_type, retrieval_strategy)
    retrieval_cfg = config_registry.get_rag_config().retrieval
    profile = retrieval_cfg.profiles.get(retrieval_complexity) or retrieval_cfg.profiles["standard"]
    final_top_k = int(profile.final_top_k)
    llm_reference_top_k = (
        int(profile.llm_reference_top_k)
        if profile.llm_reference_top_k is not None
        else final_top_k
    )
    text_enabled, graph_enabled_by_strategy = _strategy_channels(selected_strategy)
    graph_plan = _build_graph_plan(
        question_type=question_type,
        retrieval_strategy=selected_strategy,
        graph_limit=int(profile.graph_limit),
    )
    graph_plan = {
        **graph_plan,
        "enabled": bool(graph_plan.get("enabled")) and graph_enabled_by_strategy,
    }
    return {
        "rewrite": _build_rewrite_plan(question_type, retrieval_complexity),
        "mode": selected_strategy,
        "channels": {
            "vector": {"enabled": text_enabled, "recall_k": int(profile.recall_k) if text_enabled else 0},
            "lexical": {"enabled": text_enabled, "lexical_k": int(profile.lexical_k) if text_enabled else 0},
            "graph": graph_plan,
        },
        "rerank": {"enabled": bool(profile.rerank_enabled), "top_k": final_top_k},
        "context": {
            "final_top_k": final_top_k,
            "budget_chars": int(profile.context_budget),
            "llm_reference_top_k": llm_reference_top_k,
        },
        "retrieval_complexity": retrieval_complexity,
        "fusion": _build_fusion_plan(
            question_type=question_type,
            retrieval_strategy=selected_strategy,
        ),
    }
