"""Adaptive retrieval planning node for end-user knowledge-base chat."""

from __future__ import annotations

import re
from typing import Any, Callable

from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.agents.common.retrieval import pick_query_from_state
from app.agents.states import KbChatState
from app.core.llm import get_llm_for_planner

Intent = str
Complexity = str

ALLOWED_INTENTS: set[Intent] = {
    "chitchat",
    "kb_lookup",
    "procedural",
    "comparison",
    "summary",
    "ambiguous_followup",
    "out_of_scope",
}
ALLOWED_COMPLEXITIES: set[Complexity] = {"simple", "normal", "complex"}

DEFAULT_INTENT: Intent = "kb_lookup"
DEFAULT_COMPLEXITY: Complexity = "normal"
DEFAULT_REASON = "Fallback default policy."

_POLICY_TABLE: dict[tuple[Intent, Complexity], dict[str, int | bool]] = {
    ("chitchat", "simple"): {
        "retrieval_required": False,
        "max_queries": 0,
        "result_limit": 0,
        "context_budget": 0,
    },
    ("kb_lookup", "simple"): {
        "retrieval_required": True,
        "max_queries": 1,
        "result_limit": 4,
        "context_budget": 6000,
    },
    ("kb_lookup", "normal"): {
        "retrieval_required": True,
        "max_queries": 2,
        "result_limit": 8,
        "context_budget": 10000,
    },
    ("kb_lookup", "complex"): {
        "retrieval_required": True,
        "max_queries": 3,
        "result_limit": 10,
        "context_budget": 12000,
    },
    ("procedural", "simple"): {
        "retrieval_required": True,
        "max_queries": 2,
        "result_limit": 6,
        "context_budget": 8000,
    },
    ("procedural", "normal"): {
        "retrieval_required": True,
        "max_queries": 2,
        "result_limit": 8,
        "context_budget": 10000,
    },
    ("procedural", "complex"): {
        "retrieval_required": True,
        "max_queries": 3,
        "result_limit": 10,
        "context_budget": 12000,
    },
    ("comparison", "simple"): {
        "retrieval_required": True,
        "max_queries": 3,
        "result_limit": 8,
        "context_budget": 10000,
    },
    ("comparison", "normal"): {
        "retrieval_required": True,
        "max_queries": 3,
        "result_limit": 10,
        "context_budget": 10000,
    },
    ("comparison", "complex"): {
        "retrieval_required": True,
        "max_queries": 4,
        "result_limit": 12,
        "context_budget": 12000,
    },
    ("summary", "simple"): {
        "retrieval_required": True,
        "max_queries": 2,
        "result_limit": 8,
        "context_budget": 10000,
    },
    ("summary", "normal"): {
        "retrieval_required": True,
        "max_queries": 3,
        "result_limit": 10,
        "context_budget": 12000,
    },
    ("summary", "complex"): {
        "retrieval_required": True,
        "max_queries": 4,
        "result_limit": 12,
        "context_budget": 12000,
    },
    ("ambiguous_followup", "simple"): {
        "retrieval_required": True,
        "max_queries": 3,
        "result_limit": 8,
        "context_budget": 10000,
    },
    ("ambiguous_followup", "normal"): {
        "retrieval_required": True,
        "max_queries": 3,
        "result_limit": 8,
        "context_budget": 10000,
    },
    ("ambiguous_followup", "complex"): {
        "retrieval_required": True,
        "max_queries": 4,
        "result_limit": 10,
        "context_budget": 12000,
    },
    ("out_of_scope", "simple"): {
        "retrieval_required": False,
        "max_queries": 0,
        "result_limit": 0,
        "context_budget": 0,
    },
    ("out_of_scope", "normal"): {
        "retrieval_required": False,
        "max_queries": 0,
        "result_limit": 0,
        "context_budget": 0,
    },
    ("out_of_scope", "complex"): {
        "retrieval_required": False,
        "max_queries": 0,
        "result_limit": 0,
        "context_budget": 0,
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


def _normalize_label(value: Any) -> str:
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
You are planning retrieval for a knowledge-base QA system.

Classify the current user question. Return JSON only.

Rules:
- Do not answer the user.
- Do not rewrite or normalize the user question.
- Do not create retrieval queries.
- Choose only one allowed intent and one allowed complexity.
- Use recent chat history only to identify context-dependent follow-up questions.
- If a message includes a business, policy, process, document, or knowledge-base question,
  do not classify it as chitchat even if it starts with a greeting or thanks.

Allowed intent values:
- chitchat: pure greeting or thanks with no business question
- kb_lookup: ordinary knowledge-base lookup
- procedural: asks how to do something, steps, process, application, approval, setup
- comparison: asks differences, comparison, conflicts, multiple subjects
- summary: asks to summarize, list, organize, collect requirements or notes
- ambiguous_followup: short follow-up depending on earlier conversation
- out_of_scope: clearly unrelated to knowledge-base QA

Allowed complexity values:
- simple: narrow single-fact or pure chitchat
- normal: typical single-topic question
- complex: multi-subject, comparison, summary, conflict, or broad procedural question

Return this JSON shape:
{{"intent": "kb_lookup", "complexity": "normal", "reason": "short reason"}}

Examples:
- User: 帮我写一首歌
  Output: {{"intent": "out_of_scope", "complexity": "simple", "reason": "用户请求歌曲创作，不属于知识库问答范围。"}}
- User: 帮我写一首诗
  Output: {{"intent": "out_of_scope", "complexity": "simple", "reason": "用户请求诗歌创作，不属于知识库问答范围。"}}

Conversation summary:
{summary_text}

Recent chat history:
{history_text}

Current user question:
{query.strip()}
""".strip()


def build_adaptive_policy(
    *,
    query: str,
    intent: Any,
    complexity: Any,
    reason: Any = "",
) -> dict[str, Any]:
    """Map planner labels into bounded retrieval parameters."""

    resolved_intent = _normalize_label(intent)
    resolved_complexity = _normalize_label(complexity)
    resolved_reason = _compact_text(str(reason or ""), limit=240) or DEFAULT_REASON

    if resolved_intent not in ALLOWED_INTENTS:
        resolved_intent = DEFAULT_INTENT
    if resolved_complexity not in ALLOWED_COMPLEXITIES:
        resolved_complexity = DEFAULT_COMPLEXITY

    if resolved_intent == "chitchat":
        resolved_complexity = "simple"

    policy_values = _POLICY_TABLE.get(
        (resolved_intent, resolved_complexity),
        _POLICY_TABLE[(DEFAULT_INTENT, DEFAULT_COMPLEXITY)],
    )
    return {
        "intent": resolved_intent,
        "complexity": resolved_complexity,
        "retrieval_required": bool(policy_values["retrieval_required"]),
        "max_queries": int(policy_values["max_queries"]),
        "result_limit": int(policy_values["result_limit"]),
        "context_budget": int(policy_values["context_budget"]),
        "reason": resolved_reason,
    }


def build_default_adaptive_policy(query: str, *, reason: str = DEFAULT_REASON) -> dict[str, Any]:
    return build_adaptive_policy(
        query=query,
        intent=DEFAULT_INTENT,
        complexity=DEFAULT_COMPLEXITY,
        reason=reason,
    )


async def build_llm_adaptive_policy(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Ask the planner LLM for labels and convert them into a retrieval policy."""

    if not query.strip():
        return build_default_adaptive_policy(query, reason="Empty query fallback policy.")

    try:
        llm = (
            llm_factory()
            if llm_factory is not None
            else get_llm_for_planner(
                temperature=0,
                max_tokens=300,
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
        return build_adaptive_policy(
            query=query,
            intent=parsed.get("intent"),
            complexity=parsed.get("complexity"),
            reason=parsed.get("reason"),
        )
    except Exception as exc:
        logger.warning("KB chat plan_query failed, using default adaptive policy: {}", exc)
        return build_default_adaptive_policy(query)


async def user_kb_plan_query_node(state: KbChatState) -> dict[str, Any]:
    """Plan retrieval strength for the current KB chat turn."""

    query = pick_query_from_state(state, "query")
    policy = await build_llm_adaptive_policy(
        query,
        chat_history=state.get("chat_history") or [],
        memory_summary=state.get("memory_summary"),
    )
    logger.info(
        "[知识库规划] 类型={} 复杂度={} 是否检索={} 查询数上限={} 结果上限={} 上下文预算={} 原因={}",
        policy.get("intent"),
        policy.get("complexity"),
        policy.get("retrieval_required"),
        policy.get("max_queries"),
        policy.get("result_limit"),
        policy.get("context_budget"),
        policy.get("reason"),
    )
    return {"adaptive_policy": policy}
