"""Retrieval planning node for end-user knowledge-base chat."""

from __future__ import annotations

import re
from time import perf_counter
from typing import Any, Callable

from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.agents.common.retrieval import pick_query_from_state
from app.agents.states import KbChatState
from app.core.llm import get_llm_for_planner

PlanName = str

ALLOWED_PLAN_NAMES: set[PlanName] = {
    "chitchat",
    "out_of_scope",
    "fast_lookup",
    "followup_lookup",
    "procedural_lookup",
    "compare_lookup",
    "summary_lookup",
}
DEFAULT_PLAN_NAME: PlanName = "fast_lookup"
DEFAULT_REASON = "Fallback retrieval plan."

PLAN_TEMPLATES: dict[PlanName, dict[str, Any]] = {
    "chitchat": {
        "retrieval_required": False,
        "rewrite": {
            "enabled": False,
            "mode": "skip",
            "max_queries": 0,
            "strategies": [],
        },
        "retrieval": {
            "mode": "none",
            "recall_k": 0,
            "lexical_k": 0,
            "rerank_enabled": False,
            "final_top_k": 0,
            "llm_reference_top_k": 0,
            "context_budget": 0,
        },
        "answer": {
            "response_mode": "chitchat",
            "grounded_only": False,
        },
    },
    "out_of_scope": {
        "retrieval_required": False,
        "rewrite": {
            "enabled": False,
            "mode": "skip",
            "max_queries": 0,
            "strategies": [],
        },
        "retrieval": {
            "mode": "none",
            "recall_k": 0,
            "lexical_k": 0,
            "rerank_enabled": False,
            "final_top_k": 0,
            "llm_reference_top_k": 0,
            "context_budget": 0,
        },
        "answer": {
            "response_mode": "out_of_scope",
            "grounded_only": False,
        },
    },
    "fast_lookup": {
        "retrieval_required": True,
        "rewrite": {
            "enabled": False,
            "mode": "skip",
            "max_queries": 1,
            "strategies": [],
        },
        "retrieval": {
            "mode": "hybrid",
            "recall_k": 24,
            "lexical_k": 16,
            "rerank_enabled": False,
            "final_top_k": 8,
            "llm_reference_top_k": 6,
            "context_budget": 8000,
        },
        "answer": {
            "response_mode": "grounded",
            "grounded_only": True,
        },
    },
    "followup_lookup": {
        "retrieval_required": True,
        "rewrite": {
            "enabled": True,
            "mode": "heuristic",
            "max_queries": 2,
            "strategies": ["context_completion", "query_compaction"],
        },
        "retrieval": {
            "mode": "vector",
            "recall_k": 12,
            "lexical_k": 0,
            "rerank_enabled": False,
            "final_top_k": 6,
            "llm_reference_top_k": 4,
            "context_budget": 9000,
        },
        "answer": {
            "response_mode": "grounded",
            "grounded_only": True,
        },
    },
    "procedural_lookup": {
        "retrieval_required": True,
        "rewrite": {
            "enabled": True,
            "mode": "heuristic",
            "max_queries": 2,
            "strategies": ["terminology_normalization", "query_compaction"],
        },
        "retrieval": {
            "mode": "hybrid",
            "recall_k": 14,
            "lexical_k": 8,
            "rerank_enabled": False,
            "final_top_k": 6,
            "llm_reference_top_k": 4,
            "context_budget": 9000,
        },
        "answer": {
            "response_mode": "grounded",
            "grounded_only": True,
        },
    },
    "compare_lookup": {
        "retrieval_required": True,
        "rewrite": {
            "enabled": True,
            "mode": "llm",
            "max_queries": 3,
            "strategies": ["multi_aspect_split", "terminology_normalization"],
        },
        "retrieval": {
            "mode": "hybrid",
            "recall_k": 18,
            "lexical_k": 10,
            "rerank_enabled": True,
            "final_top_k": 8,
            "llm_reference_top_k": 5,
            "context_budget": 10000,
        },
        "answer": {
            "response_mode": "grounded",
            "grounded_only": True,
        },
    },
    "summary_lookup": {
        "retrieval_required": True,
        "rewrite": {
            "enabled": True,
            "mode": "llm",
            "max_queries": 3,
            "strategies": ["multi_aspect_split", "terminology_normalization"],
        },
        "retrieval": {
            "mode": "hybrid",
            "recall_k": 20,
            "lexical_k": 12,
            "rerank_enabled": True,
            "final_top_k": 8,
            "llm_reference_top_k": 5,
            "context_budget": 11000,
        },
        "answer": {
            "response_mode": "grounded",
            "grounded_only": True,
        },
    },
}


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content or "")


def _compact_text(text: str, *, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit].strip()


def _normalize_plan_name(value: Any) -> str:
    return re.sub(r"\s+", "_", str(value or "").strip().lower())


def _format_recent_history(chat_history: list[dict[str, Any]] | None, *, limit: int = 4) -> str:
    lines: list[str] = []
    for item in list(chat_history or [])[-limit:]:
        role = _compact_text(str(item.get("role") or "assistant"), limit=24) or "assistant"
        content = _compact_text(str(item.get("content") or ""), limit=300)
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) or "(none)"


def _build_planner_prompt(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None,
    memory_summary: str | None,
) -> str:
    history_text = _format_recent_history(chat_history)
    summary_text = _compact_text(memory_summary or "", limit=600) or "(none)"
    return f"""
You are routing a user question to one retrieval plan for a knowledge-base QA system.

Return JSON only:
{{"plan_name": "fast_lookup", "reason": "short reason"}}

Choose exactly one plan_name from:
- chitchat: greeting, thanks, or small talk with no business question
- out_of_scope: unrelated to the knowledge base or asks for open-ended creation
- fast_lookup: clear single-topic knowledge lookup
- followup_lookup: short follow-up that depends on recent conversation context
- procedural_lookup: asks for steps, workflow, setup, process, or how-to guidance
- compare_lookup: asks for differences, tradeoffs, conflicts, or multiple subjects
- summary_lookup: asks to summarize, organize, collect, or aggregate information

Rules:
- Do not answer the user.
- Do not rewrite the question.
- Prefer fast_lookup unless there is a clear reason to use another plan.
- Use followup_lookup only when the question depends on prior context.
- Use compare_lookup only for true comparisons or multiple entities.
- Use summary_lookup only for collection, synthesis, or summarization requests.

Conversation summary:
{summary_text}

Recent chat history:
{history_text}

Current user question:
{query.strip()}
""".strip()


def build_retrieval_plan(
    *,
    plan_name: Any,
    reason: Any = "",
) -> dict[str, Any]:
    resolved_plan_name = _normalize_plan_name(plan_name)
    if resolved_plan_name not in ALLOWED_PLAN_NAMES:
        resolved_plan_name = DEFAULT_PLAN_NAME
    resolved_reason = _compact_text(str(reason or ""), limit=240) or DEFAULT_REASON
    template = PLAN_TEMPLATES[resolved_plan_name]
    return {
        "plan_name": resolved_plan_name,
        "reason": resolved_reason,
        "retrieval_required": bool(template["retrieval_required"]),
        "rewrite": {
            "enabled": bool(template["rewrite"]["enabled"]),
            "mode": str(template["rewrite"]["mode"]),
            "max_queries": int(template["rewrite"]["max_queries"]),
            "strategies": list(template["rewrite"]["strategies"]),
        },
        "retrieval": {
            "mode": str(template["retrieval"]["mode"]),
            "recall_k": int(template["retrieval"]["recall_k"]),
            "lexical_k": int(template["retrieval"]["lexical_k"]),
            "rerank_enabled": bool(template["retrieval"]["rerank_enabled"]),
            "final_top_k": int(template["retrieval"]["final_top_k"]),
            "llm_reference_top_k": int(template["retrieval"]["llm_reference_top_k"]),
            "context_budget": int(template["retrieval"]["context_budget"]),
        },
        "answer": {
            "response_mode": str(template["answer"]["response_mode"]),
            "grounded_only": bool(template["answer"]["grounded_only"]),
        },
    }


def build_default_retrieval_plan(*, reason: str = DEFAULT_REASON) -> dict[str, Any]:
    return build_retrieval_plan(plan_name=DEFAULT_PLAN_NAME, reason=reason)


async def build_llm_retrieval_plan(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    if not query.strip():
        return build_default_retrieval_plan(reason="Empty query fallback plan.")

    llm = (
        llm_factory()
        if llm_factory is not None
        else get_llm_for_planner(
            temperature=0,
            max_tokens=200,
        )
    )
    response = await llm.ainvoke(
        _build_planner_prompt(
            query,
            chat_history=chat_history,
            memory_summary=memory_summary,
        )
    )
    parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    return build_retrieval_plan(
        plan_name=parsed.get("plan_name"),
        reason=parsed.get("reason"),
    )


async def user_kb_plan_query_node(state: KbChatState) -> dict[str, Any]:
    """Build the retrieval plan for the current KB chat turn."""

    query = pick_query_from_state(state, "query")
    started_at = perf_counter()
    try:
        retrieval_plan = await build_llm_retrieval_plan(
            query,
            chat_history=state.get("chat_history") or [],
            memory_summary=state.get("memory_summary"),
        )
    except Exception as exc:
        logger.warning("KB chat plan_query failed, using default retrieval plan: {}", exc)
        retrieval_plan = build_default_retrieval_plan()

    latency_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "[KB Plan] plan={} retrieval_required={} rewrite_mode={} retrieval_mode={} rerank={} latency_ms={} reason={}",
        retrieval_plan.get("plan_name"),
        retrieval_plan.get("retrieval_required"),
        (retrieval_plan.get("rewrite") or {}).get("mode"),
        (retrieval_plan.get("retrieval") or {}).get("mode"),
        (retrieval_plan.get("retrieval") or {}).get("rerank_enabled"),
        latency_ms,
        retrieval_plan.get("reason"),
    )
    return {"retrieval_plan": retrieval_plan}
