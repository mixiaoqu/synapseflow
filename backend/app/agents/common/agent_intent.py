"""Top-level intent routing helper for agent workflows."""

from __future__ import annotations

import re
from typing import Any, Callable

from app.agents.common.llm_json import parse_llm_json_object
from app.core.llm import get_llm_for_planner

ALLOWED_INTENT_TYPES = {"knowledge_qa", "clarify", "direct_answer"}
ALLOWED_DIRECT_ANSWER_KINDS = {"chitchat", "out_of_scope"}


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content or "")


def _compact_text(text: str, *, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit].strip()


def _normalize_choice(value: Any, allowed: set[str], default: str) -> str:
    normalized = re.sub(r"\s+", "_", str(value or "").strip().lower())
    return normalized if normalized in allowed else default


def _coerce_string_list(value: Any, *, item_limit: int = 80) -> list[str]:
    if isinstance(value, str):
        raw_items = [value]
    else:
        raw_items = list(value or [])
    return [
        _compact_text(str(item), limit=item_limit)
        for item in raw_items
        if _compact_text(str(item), limit=item_limit)
    ]


def _build_prompt(
    query: str,
    *,
    chat_history: list[dict[str, Any]],
    memory_summary: str | None,
    page_type: str | None,
) -> str:
    history = "\n".join(
        f"{item.get('role', 'user')}: {_compact_text(str(item.get('content') or ''), limit=240)}"
        for item in chat_history[-4:]
        if str(item.get("content") or "").strip()
    )
    return f"""
You route one user turn for the top-level agent workflow.

Return JSON only:
{{
  "intent_type": "knowledge_qa",
  "needs_clarification": false,
  "missing_fields": [],
  "direct_answer_kind": null,
  "reason": "short reason"
}}

Allowed intent_type values:
- knowledge_qa
- clarify
- direct_answer

Allowed direct_answer_kind values when intent_type=direct_answer:
- chitchat
- out_of_scope

Rules:
- Do not answer the user.
- Decide only the top-level route: knowledge QA, clarification, or direct reply.
- Do not classify the knowledge question type.
- Do not extract entities.
- Do not choose retrieval strategy, graph strategy, top-k, or rerank policy.
- Use knowledge_qa when the user asks about content that should be answered from the current knowledge base or conversation context.
- Use clarify only when the request is too incomplete to choose a route, such as an empty question or unresolved reference with no usable context.
- Use direct_answer only for greetings, simple social turns, or requests clearly outside knowledge-base answering.

Page type:
{page_type or "(none)"}

Conversation summary:
{_compact_text(memory_summary or "", limit=600) or "(none)"}

Recent history:
{history or "(none)"}

User question:
{query.strip()}
""".strip()


async def build_agent_intent(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    page_type: str | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Classify the user turn for top-level agent routing only."""

    if not query.strip():
        return {
            "type": "clarify",
            "needs_clarification": True,
            "missing_fields": ["query"],
            "direct_answer_kind": None,
            "reason": "用户问题为空，需要补齐问题内容。",
        }

    llm = llm_factory() if llm_factory is not None else get_llm_for_planner(
        temperature=0,
        max_tokens=160,
    )
    response = await llm.ainvoke(
        _build_prompt(
            query,
            chat_history=list(chat_history or []),
            memory_summary=memory_summary,
            page_type=page_type,
        )
    )
    parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    intent_type = _normalize_choice(
        parsed.get("intent_type") or parsed.get("type"),
        ALLOWED_INTENT_TYPES,
        "knowledge_qa",
    )
    needs_clarification = bool(parsed.get("needs_clarification"))
    missing_fields = _coerce_string_list(parsed.get("missing_fields"), item_limit=80)
    if needs_clarification or missing_fields:
        intent_type = "clarify"

    direct_answer_kind = None
    if intent_type == "direct_answer":
        direct_answer_kind = _normalize_choice(
            parsed.get("direct_answer_kind"),
            ALLOWED_DIRECT_ANSWER_KINDS,
            "out_of_scope",
        )

    return {
        "type": intent_type,
        "needs_clarification": intent_type == "clarify",
        "missing_fields": missing_fields,
        "direct_answer_kind": direct_answer_kind,
        "reason": _compact_text(str(parsed.get("reason") or ""), limit=240)
        or "主图已完成意图路由判断。",
    }
