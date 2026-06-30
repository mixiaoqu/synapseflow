"""Question analysis helper for the knowledge_qa workflow."""

from __future__ import annotations

import re
from typing import Any, Callable

from app.agents.common.llm_json import parse_llm_json_object
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


def _coerce_string_list(value: Any, *, item_limit: int = 120) -> list[str]:
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
You analyze one knowledge-base question after the top-level agent has already routed it to knowledge QA.

Return JSON only:
{{
  "question_type": "attribute_lookup",
  "retrieval_complexity": "standard",
  "entities": ["Order", "User"],
  "needs_path": false,
  "needs_relation": false,
  "needs_summary": false,
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

Allowed retrieval_complexity values:
- fast
- standard
- broad

Rules:
- Do not answer the user.
- Do not decide whether knowledge QA is needed; this workflow is already inside knowledge QA.
- Do not choose retrieval strategy, graph strategy, top-k, or rerank policy.
- Classify the question type and complexity so the next node can plan retrieval.
- Use summary_lookup for broad overviews, summaries, or multi-aspect synthesis.
- Use relationship_lookup for explicit relations, ownership, association, or multi-entity reasoning.
- Use dependency_lookup for dependency direction questions.
- Use call_chain_lookup for call chain or invocation path questions.
- Use flow_lookup for process, lifecycle, or end-to-end flow questions.
- Use location_lookup when the user asks where a capability, file, function, table, or config lives.
- Use attribute_lookup for properties, structure, fields, config items, state, values, or schema-like questions.
- Use definition_lookup for concepts, meanings, definitions, or plain explanations.
- Extract concrete entities mentioned by the user, such as class/function/table/module/file/config names.
- Set needs_path=true when the answer needs file/function/module location.
- Set needs_relation=true when the answer needs dependency, call, ownership, or association evidence.
- Set needs_summary=true when the answer needs a module/file/model/process summary.
- retrieval_complexity indicates task scope and complexity, not retrieval strategy.
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


async def build_knowledge_question_analysis(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    page_type: str | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Analyze a question already routed into the knowledge_qa workflow."""

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
    retrieval_complexity = _normalize_choice(
        parsed.get("retrieval_complexity"),
        ALLOWED_RETRIEVAL_COMPLEXITIES,
        "standard",
    )
    entities = _coerce_string_list(parsed.get("entities"), item_limit=120)
    return {
        "question_type": question_type,
        "retrieval_complexity": retrieval_complexity,
        "entities": entities,
        "needs_path": bool(parsed.get("needs_path")),
        "needs_relation": bool(parsed.get("needs_relation")),
        "needs_summary": bool(parsed.get("needs_summary")),
        "reason": _compact_text(str(parsed.get("reason") or ""), limit=240)
        or "知识库子图已完成问题类型分析。",
    }
