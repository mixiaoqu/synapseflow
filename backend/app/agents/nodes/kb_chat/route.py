"""Route helper for knowledge-base chat."""

from __future__ import annotations

import re
from time import perf_counter
from typing import Any, Callable

from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatState
from app.core.llm import get_llm_for_planner

ALLOWED_QUESTION_TYPES = {
    "summary_lookup",
    "relationship_lookup",
    "dependency_lookup",
    "call_chain_lookup",
    "flow_lookup",
    "location_lookup",
    "attribute_lookup",
    "definition_lookup",
    "chitchat",
    "out_of_scope",
}
ALLOWED_RETRIEVAL_COMPLEXITIES = {"fast", "standard", "broad"}
ALLOWED_RETRIEVAL_STRATEGIES = {"auto", "skip"}


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
  "question_type": "summary_lookup",
  "retrieval_complexity": "standard",
  "entities": ["Order", "User"],
  "needs_path": false,
  "needs_relation": false,
  "needs_summary": true,
  "needs_clarification": false,
  "reason": "short reason"
}}

Allowed question_type values:
- summary_lookup
- relationship_lookup
- attribute_lookup
- definition_lookup
- location_lookup
- flow_lookup
- dependency_lookup
- call_chain_lookup
- chitchat
- out_of_scope

Allowed retrieval_complexity values:
- fast
- standard
- broad

Rules:
- Do not answer the user.
- Classify the user's retrieval intent. Do not decide how retrieval should execute.
- Use summary_lookup for broad overviews, summaries, or multi-aspect synthesis.
- Use relationship_lookup for explicit relations, dependencies, ownership, or multi-entity reasoning.
- Use dependency_lookup for dependency direction questions.
- Use call_chain_lookup for call chain or invocation path questions.
- Use flow_lookup for process, lifecycle, or end-to-end flow questions.
- Use location_lookup when the user asks where a capability, file, function, table, or config lives.
- Use attribute_lookup for pure properties, structure, fields, state, values, or schema-like questions.
- Use definition_lookup for concepts, meanings, definitions, or plain explanations.
- Extract concrete entities mentioned by the user, such as class/function/table/module/file names.
- Set needs_path=true when the answer needs file/function/module location.
- Set needs_relation=true when the answer needs dependency, call, ownership, or association evidence.
- Set needs_summary=true when the answer needs a module/file/model/process summary.
- retrieval_complexity indicates retrieval scope and complexity, not question type.
- Prefer fast for precise single-target lookups.
- Prefer broad for overviews, multi-aspect comparisons, or complex follow-ups.
- Mark needs_clarification=true only when the question lacks a core entity or has unresolved references.

Page type:
{page_type or "(none)"}

Conversation summary:
{_compact_text(memory_summary or "", limit=600) or "(none)"}

Recent history:
{history or "(none)"}

User question:
{query.strip()}
""".strip()


async def build_kb_chat_route(
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
            "retrieval_strategy": "skip",
            "retrieval_complexity": "fast",
            "retrieval_required": False,
            "needs_clarification": False,
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
        "definition_lookup",
    )
    raw_strategy = str(parsed.get("retrieval_strategy") or "").strip().lower()
    if question_type in {"chitchat", "out_of_scope"}:
        retrieval_strategy = "skip"
    elif raw_strategy in ALLOWED_RETRIEVAL_STRATEGIES:
        retrieval_strategy = raw_strategy
    else:
        retrieval_strategy = "auto"

    retrieval_complexity = _normalize_choice(
        parsed.get("retrieval_complexity"),
        ALLOWED_RETRIEVAL_COMPLEXITIES,
        "standard",
    )
    needs_clarification = bool(parsed.get("needs_clarification"))
    entities = [
        _compact_text(str(item), limit=120)
        for item in list(parsed.get("entities") or [])
        if _compact_text(str(item), limit=120)
    ]
    return {
        "question_type": question_type,
        "retrieval_strategy": retrieval_strategy,
        "retrieval_complexity": retrieval_complexity,
        "retrieval_required": retrieval_strategy != "skip",
        "entities": entities,
        "needs_path": bool(parsed.get("needs_path")),
        "needs_relation": bool(parsed.get("needs_relation")),
        "needs_summary": bool(parsed.get("needs_summary")),
        "needs_clarification": needs_clarification,
        "reason": _compact_text(str(parsed.get("reason") or ""), limit=240)
        or "Router selected the route.",
    }


async def kb_chat_route_node(
    state: KbChatState,
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
        route = await build_kb_chat_route(
            str(state.get("query") or ""),
            chat_history=list(state.get("chat_history") or []),
            memory_summary=state.get("memory_summary"),
            page_type=page_context.get("page_type") or page_config.get("page_type"),
            llm_factory=llm_factory,
        )
    except Exception as exc:
        logger.exception("kb_chat route failed")
        raise RuntimeError("kb_chat route failed") from exc

    return {
        "question_type": route["question_type"],
        "retrieval_strategy": route["retrieval_strategy"],
        "retrieval_complexity": route["retrieval_complexity"],
        "retrieval_required": route["retrieval_required"],
        "candidate_entities": route.get("entities") or [],
        "needs_clarification": route["needs_clarification"],
        "route_reason": route["reason"],
        "route_trace": {"latency_ms": int((perf_counter() - started_at) * 1000)},
    }
