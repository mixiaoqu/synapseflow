"""Retrieval query rewrite helpers for KB chat."""

from __future__ import annotations

import re
from typing import Any, Callable

from loguru import logger

from app.core.llm import get_llm_for_analysis
from app.utils import extract_json_from_llm_response

_MAX_RETRIEVAL_QUERIES = 4
_MAX_QUERY_LENGTH = 160

_CODE_TOKEN_PATTERN = re.compile(
    r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'|《([^》]+)》|([A-Za-z0-9_./:-]{3,})"
)
_RUNTIME_REFERENCE_PATTERN = re.compile(
    r"(当前页面|这个页面|该页面|本页面|当前页|这个页|本页|这里)"
)


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


def _normalize_query(text: str) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    return value[:_MAX_QUERY_LENGTH].strip()


def _dedupe_keep_order(items: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _normalize_query(item)
        key = normalized.casefold()
        if len(normalized) < 2 or key in seen:
            continue
        out.append(normalized)
        seen.add(key)
        if len(out) >= limit:
            break
    return out


def _extract_protected_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for match in _CODE_TOKEN_PATTERN.finditer(text or ""):
        token = next((group for group in match.groups() if group), "")
        cleaned = _normalize_query(token.strip("`\"'"))
        if len(cleaned) < 2:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        tokens.append(cleaned)
        seen.add(key)
    return tokens


def _format_runtime_context(runtime_context: dict[str, Any] | None) -> str:
    if not isinstance(runtime_context, dict):
        return "(none)"

    page_name = _normalize_query(str(runtime_context.get("page_name") or ""))
    page_type = _normalize_query(str(runtime_context.get("page_type") or ""))
    page_description = _normalize_query(str(runtime_context.get("page_description") or ""))
    lines = []
    if page_name:
        lines.append(f"Page name: {page_name}")
    if page_type:
        lines.append(f"Page type: {page_type}")
    if page_description:
        lines.append(f"Page description: {page_description}")
    return "\n".join(lines) or "(none)"


def _runtime_contextual_query(query: str, runtime_context: dict[str, Any] | None) -> str:
    if not _RUNTIME_REFERENCE_PATTERN.search(query):
        return ""

    page_name = ""
    if isinstance(runtime_context, dict):
        page_name = _normalize_query(str(runtime_context.get("page_name") or ""))
    if not page_name or page_name in query:
        return ""
    return _normalize_query(f"{page_name} {query}")


def _recent_user_context(chat_history: list[dict[str, str]] | None, *, limit: int = 2) -> str:
    recent = [
        _normalize_query(str(item.get("content") or ""))
        for item in list(chat_history or [])
        if str(item.get("role") or "").strip().lower() == "user"
    ]
    recent = [item for item in recent if item]
    return " | ".join(recent[-limit:])


def _build_fallback_queries(
    query: str,
    *,
    chat_history: list[dict[str, str]] | None,
    memory_summary: str | None,
    runtime_context: dict[str, Any] | None,
    limit: int,
) -> list[str]:
    original = _normalize_query(query)
    if not original:
        return []

    candidates = [original]
    runtime_query = _runtime_contextual_query(original, runtime_context)
    if runtime_query:
        candidates.insert(0, runtime_query)

    recent_user_context = _recent_user_context(chat_history)
    summary = _normalize_query(memory_summary or "")
    if recent_user_context:
        candidates.append(_normalize_query(f"{recent_user_context} {original}"))
    if summary:
        candidates.append(_normalize_query(f"{summary} {original}"))
    return _dedupe_keep_order(candidates, limit=limit)


def _build_rewrite_prompt(
    query: str,
    *,
    question_type: str,
    retrieval_label: str,
    max_queries: int,
    chat_history: list[dict[str, str]] | None = None,
    memory_summary: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    protected_tokens: list[str] | None = None,
) -> str:
    history_lines = []
    for item in list(chat_history or [])[-4:]:
        role = str(item.get("role") or "").strip().lower() or "assistant"
        content = _normalize_query(str(item.get("content") or ""))
        if not content:
            continue
        history_lines.append(f"{role.title()}: {content}")

    protected = ", ".join(protected_tokens or []) or "(none)"
    summary_text = _normalize_query(memory_summary or "") or "(none)"
    context_text = "\n".join(history_lines) or "(none)"
    runtime_context_text = _format_runtime_context(runtime_context)
    return f"""
You are rewriting a single user question into retrieval-focused queries for a knowledge base.

Return JSON only:
{{
  "queries": ["query 1", "query 2"],
  "candidate_entities": ["entity 1", "entity 2"]
}}

Rules:
- Do not answer the question.
- Do not invent facts.
- Return at most {max_queries} queries.
- Preserve these protected tokens exactly when relevant: {protected}
- question_type determines the rewrite policy.
- retrieval_label controls retrieval breadth: fast = minimal expansion, standard = balanced, broad = wider coverage.
- followup_lookup must resolve short references from recent history when possible.
- procedural_lookup should favor process, step, setup, or handling terms.
- relationship_lookup should favor relation, dependency, ownership, or connection phrasing.
- compare_lookup should prefer comparison-oriented queries.
- summary_lookup can include multi-aspect overview queries.
- candidate_entities should contain the main entities, modules, products,流程名, or objects mentioned in the question or rewritten queries.
- Return empty arrays if nothing is explicit.

Question type: {question_type}
Retrieval label: {retrieval_label}

Conversation summary:
{summary_text}

Recent chat turns:
{context_text}

User environment:
{runtime_context_text}

User question:
{query}
""".strip()


def _validate_queries(
    *,
    original: str,
    queries: list[str],
    protected_tokens: list[str],
    limit: int,
) -> list[str]:
    normalized = _dedupe_keep_order([original, *queries], limit=limit)
    if not normalized:
        return []

    if protected_tokens:
        joined = " || ".join(normalized)
        for token in protected_tokens[:8]:
            if token not in joined and token.casefold() in original.casefold():
                raise ValueError(f"protected token missing from rewrite result: {token}")
    return normalized


async def build_kb_chat_retrieval_queries(
    query: str,
    *,
    chat_history: list[dict[str, str]] | None = None,
    memory_summary: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
    mode: str | None = None,
    question_type: str = "entity_lookup",
    retrieval_label: str = "standard",
    max_queries: int | None = None,
    strategies: list[str] | None = None,
) -> dict[str, list[str]]:
    """Build retrieval-focused queries for single-round KB chat."""

    del strategies
    del mode

    original = _normalize_query(query)
    if not original:
        return {"queries": [], "candidate_entities": []}

    limit = max(1, min(max_queries or _MAX_RETRIEVAL_QUERIES, _MAX_RETRIEVAL_QUERIES))
    protected_tokens = _extract_protected_tokens(original)
    fallback = _build_fallback_queries(
        original,
        chat_history=chat_history,
        memory_summary=memory_summary,
        runtime_context=runtime_context,
        limit=limit,
    )

    try:
        resolved_factory = llm_factory or get_llm_for_analysis
        llm = resolved_factory()
        response = await llm.ainvoke(
            _build_rewrite_prompt(
                original,
                question_type=question_type,
                retrieval_label=retrieval_label,
                max_queries=limit,
                chat_history=chat_history,
                memory_summary=memory_summary,
                runtime_context=runtime_context,
                protected_tokens=protected_tokens,
            )
        )
        parsed = extract_json_from_llm_response(_coerce_text(getattr(response, "content", response)))
        raw_queries = parsed.get("queries") or []
        llm_queries = [item for item in raw_queries if isinstance(item, str)]
        raw_entities = parsed.get("candidate_entities") or []
        llm_entities = [
            _normalize_query(item)
            for item in raw_entities
            if isinstance(item, str) and _normalize_query(item)
        ]
        validated = _validate_queries(
            original=original,
            queries=llm_queries,
            protected_tokens=protected_tokens,
            limit=limit,
        )
        return {
            "queries": validated or fallback or [original],
            "candidate_entities": _dedupe_keep_order(llm_entities, limit=8),
        }
    except Exception as exc:
        logger.warning("KB chat query rewrite failed, fallback to backup queries: {}", exc)
        return {"queries": fallback or [original], "candidate_entities": []}
