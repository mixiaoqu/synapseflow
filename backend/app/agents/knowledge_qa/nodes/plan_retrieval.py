"""Deterministic text-retrieval planning for knowledge QA."""

from __future__ import annotations

from typing import Any

from app.core.config.registry import config_registry


def build_knowledge_qa_retrieval_plan(*, retrieval_profile: str) -> dict[str, Any]:
    """Build the production text-retrieval plan from a validated profile."""

    retrieval_cfg = config_registry.get_rag_config().retrieval
    profile = retrieval_cfg.profiles.get(retrieval_profile) or retrieval_cfg.profiles["standard"]
    final_top_k = int(profile.final_top_k)
    llm_reference_top_k = (
        int(profile.llm_reference_top_k)
        if profile.llm_reference_top_k is not None
        else final_top_k
    )
    return {
        "mode": "text_only",
        "channels": {
            "vector": {"enabled": True, "recall_k": int(profile.recall_k)},
            "lexical": {"enabled": True, "lexical_k": int(profile.lexical_k)},
        },
        "rerank": {"enabled": bool(profile.rerank_enabled), "top_k": final_top_k},
        "context": {
            "final_top_k": final_top_k,
            "budget_chars": int(profile.context_budget),
            "llm_reference_top_k": llm_reference_top_k,
        },
        "retrieval_profile": retrieval_profile,
    }
