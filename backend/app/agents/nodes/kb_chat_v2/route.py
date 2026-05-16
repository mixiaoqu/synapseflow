"""Route node for kb_chat_v2."""

from __future__ import annotations

import re
from time import perf_counter
from typing import Any, Callable

from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatV2State
from app.core.llm import get_llm_for_planner

ALLOWED_QUESTION_TYPES = {
    "entity_lookup",
    "relationship_lookup",
    "procedural_lookup",
    "compare_lookup",
    "summary_lookup",
    "followup_lookup",
    "chitchat",
    "out_of_scope",
}
ALLOWED_RETRIEVAL_COMPLEXITIES = {"fast", "standard", "broad"}


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
You classify one user turn for a knowledge-base QA workflow.

Return JSON only:
{{
  "question_type": "entity_lookup",
  "retrieval_complexity": "standard",
  "retrieval_required": true,
  "reason": "short reason"
}}

Allowed question_type values:
- entity_lookup
- relationship_lookup
- procedural_lookup
- compare_lookup
- summary_lookup
- followup_lookup
- chitchat
- out_of_scope

Allowed retrieval_complexity values:
- fast
- standard
- broad

Rules:
- Do not answer the user.
- Use retrieval_required=false only for chitchat and out_of_scope.
- Use followup_lookup when the query strongly depends on prior turns or unresolved references.
- Use entity_lookup for questions about one entity, concept, module, or object.
- Use relationship_lookup for relations, dependencies, ownership, or connections between entities.
- Use procedural_lookup for process, steps, setup, or handling questions.
- Use compare_lookup for explicit differences, tradeoffs, or comparisons.
- Use summary_lookup for broad overviews or multi-aspect summaries.
- retrieval_complexity indicates retrieval scope and complexity, not question type.
- Prefer fast for precise single-target lookups.
- Prefer broad for overviews, multi-aspect comparisons, or complex follow-ups.

Page type:
{page_type or "(none)"}

Conversation summary:
{_compact_text(memory_summary or "", limit=600) or "(none)"}

Recent history:
{history or "(none)"}

User question:
{query.strip()}
""".strip()


async def build_kb_chat_v2_route(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    page_type: str | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    if not query.strip():
        return {
            "question_type": "out_of_scope",
            "retrieval_complexity": "fast",
            "retrieval_required": False,
            "reason": "Empty query.",
        }

    llm = llm_factory() if llm_factory is not None else get_llm_for_planner(
        temperature=0,
        max_tokens=240,
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
    question_type = _normalize_choice(
        parsed.get("question_type"),
        ALLOWED_QUESTION_TYPES,
        "entity_lookup",
    )
    retrieval_required = bool(parsed.get("retrieval_required"))
    if question_type in {"chitchat", "out_of_scope"}:
        retrieval_required = False
    elif not retrieval_required:
        retrieval_required = True

    retrieval_complexity = _normalize_choice(
        parsed.get("retrieval_complexity"),
        ALLOWED_RETRIEVAL_COMPLEXITIES,
        "standard",
    )
    return {
        "question_type": question_type,
        "retrieval_complexity": retrieval_complexity,
        "retrieval_required": retrieval_required,
        "reason": _compact_text(str(parsed.get("reason") or ""), limit=240)
        or "V2 router selected the route.",
    }


async def kb_chat_v2_route_node(
    state: KbChatV2State,
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    emit_progress(
        stream_writer,
        node_id="route",
        stage="route",
        message="正在理解你的问题",
    )
    page_context = dict(state.get("page_context") or {})
    page_config = dict(state.get("page_config") or {})
    started_at = perf_counter()
    try:
        route = await build_kb_chat_v2_route(
            str(state.get("query") or ""),
            chat_history=list(state.get("chat_history") or []),
            memory_summary=state.get("memory_summary"),
            page_type=page_context.get("page_type") or page_config.get("page_type"),
            llm_factory=llm_factory,
        )
    except Exception as exc:
        logger.exception("kb_chat_v2 route failed")
        raise RuntimeError("kb_chat_v2 route failed") from exc

    return {
        "question_type": route["question_type"],
        "retrieval_complexity": route["retrieval_complexity"],
        "retrieval_required": route["retrieval_required"],
        "route_reason": route["reason"],
        "route_trace": {"latency_ms": int((perf_counter() - started_at) * 1000)},
    }
