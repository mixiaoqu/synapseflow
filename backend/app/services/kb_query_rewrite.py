"""Retrieval query rewrite helpers for KB chat."""

from __future__ import annotations

import re
from typing import Any, Callable

from loguru import logger

from app.core.llm import get_llm_for_analysis
from app.utils import extract_json_from_llm_response

RewriteMode = str

_MAX_RETRIEVAL_QUERIES = 4
_MAX_QUERY_LENGTH = 160

_LEADING_FILLER_PATTERNS = [
    r"^(?:please|pls|kindly)\s+",
    r"^(?:can you|could you|would you)\s+",
    r"^(?:i want to know|tell me|help me understand)\s+",
    r"^(?:\u8bf7\u95ee|\u9ebb\u70e6|\u5e2e\u6211|\u60f3\u95ee\u4e0b|\u6211\u60f3\u77e5\u9053|\u54a8\u8be2\u4e00\u4e0b)\s*",
]
_QUESTION_TAIL_PATTERN = re.compile(
    r"(?:\?|\uFF1F|\u5417|\u4e48|\u561b|\u5462|\u5440|\u554a|\u662f\u5426|\u53ef\u5426|\u884c\u4e0d\u884c|\u53ef\u4ee5\u5417|\u80fd\u5426)\s*$",
    flags=re.IGNORECASE,
)
_QUESTION_BODY_PATTERN = re.compile(
    r"\b(?:how to|how do i|how can i|what is|where is|why is|can i|does it)\b|(?:\u600e\u4e48|\u5982\u4f55|\u4ec0\u4e48\u662f|\u54ea\u91cc|\u5728\u54ea|\u4e3a\u4ec0\u4e48|\u80fd\u4e0d\u80fd|\u662f\u5426\u652f\u6301)",
    flags=re.IGNORECASE,
)
_CODE_TOKEN_PATTERN = re.compile(
    r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'|\u300a([^\u300b]+)\u300b|([A-Za-z0-9_./:-]{3,})"
)
_CJK_COMPARE_PATTERN = re.compile(r"(\u533a\u522b|\u5dee\u5f02|\u5bf9\u6bd4|\u6bd4\u8f83)")


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


def _strip_filler_phrases(text: str) -> str:
    stripped = text.strip()
    for pattern in _LEADING_FILLER_PATTERNS:
        stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)
    stripped = _QUESTION_BODY_PATTERN.sub(" ", stripped)
    stripped = _QUESTION_TAIL_PATTERN.sub("", stripped)
    stripped = re.sub(r"[\uFF0C\u3002\uFF1B\uFF1A,;:]+", " ", stripped)
    return _normalize_query(stripped)


def _extract_code_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for match in _CODE_TOKEN_PATTERN.finditer(text or ""):
        token = next((group for group in match.groups() if group), "")
        cleaned = _normalize_query(token.strip("`\"'"))
        if len(cleaned) < 3:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        tokens.append(cleaned)
        seen.add(key)
    return tokens


def _recent_user_context(chat_history: list[dict[str, str]] | None, *, limit: int = 2) -> str:
    recent = [
        _normalize_query(str(item.get("content") or ""))
        for item in list(chat_history or [])
        if str(item.get("role") or "").strip().lower() == "user"
    ]
    recent = [item for item in recent if item]
    return " | ".join(recent[-limit:])


def _split_compare_query(original: str) -> list[str]:
    lowered = original.lower()
    if " vs " in lowered:
        parts = [item.strip() for item in re.split(r"\bvs\b", original, flags=re.IGNORECASE)]
    elif " and " in lowered and any(token in lowered for token in ("difference", "compare")):
        parts = [item.strip() for item in re.split(r"\band\b", original, flags=re.IGNORECASE)]
    elif _CJK_COMPARE_PATTERN.search(original):
        parts = [item.strip() for item in re.split(r"(?:和|与|跟|及)", original) if item.strip()]
    else:
        parts = []
    return [_normalize_query(item) for item in parts if len(_normalize_query(item)) >= 2]


def _build_heuristic_queries(
    query: str,
    *,
    chat_history: list[dict[str, str]] | None,
    memory_summary: str | None,
    limit: int,
    strategies: set[str],
) -> list[str]:
    original = _normalize_query(query)
    if not original:
        return []

    candidates: list[str] = [original]
    compact = _strip_filler_phrases(original)
    code_tokens = _extract_code_tokens(original)
    if (
        "query_compaction" in strategies or "terminology_normalization" in strategies
    ) and compact and compact.casefold() != original.casefold():
        candidates.append(compact)
    if "terminology_normalization" in strategies and code_tokens:
        candidates.append(" ".join(code_tokens[:3]))
        if compact:
            candidates.append(_normalize_query(f"{compact} {' '.join(code_tokens[:2])}"))
    if "context_completion" in strategies:
        recent_user_context = _recent_user_context(chat_history)
        summary = _normalize_query(memory_summary or "")
        if recent_user_context:
            candidates.append(_normalize_query(f"{recent_user_context} {original}"))
        if summary:
            candidates.append(_normalize_query(f"{summary} {original}"))
    if "multi_aspect_split" in strategies:
        candidates.extend(_split_compare_query(original))
    return _dedupe_keep_order(candidates, limit=limit)


def _build_rewrite_prompt(
    query: str,
    *,
    max_queries: int,
    strategies: set[str],
    chat_history: list[dict[str, str]] | None = None,
    memory_summary: str | None = None,
) -> str:
    history_lines = []
    for item in list(chat_history or [])[-4:]:
        role = str(item.get("role") or "").strip().lower() or "assistant"
        content = _normalize_query(str(item.get("content") or ""))
        if not content:
            continue
        history_lines.append(f"{role.title()}: {content}")

    summary_text = _normalize_query(memory_summary or "") or "(none)"
    context_text = "\n".join(history_lines) or "(none)"
    objective_lines = {
        "context_completion": "Use recent conversation context to resolve short follow-up references when needed.",
        "terminology_normalization": "Favor canonical product, process, config, and document terminology.",
        "query_compaction": "Favor short search-style queries over natural-language questions.",
        "multi_aspect_split": "When useful, include separate queries for distinct comparison or summary subtopics.",
    }
    active_objectives = [
        f"- {objective_lines[name]}"
        for name in ("context_completion", "terminology_normalization", "query_compaction", "multi_aspect_split")
        if name in strategies
    ] or ["- Preserve the original wording unless a clearer retrieval query is obvious."]

    return f"""
You are rewriting a single user question into short retrieval-focused queries for a knowledge base.

Return JSON only:
{{"queries": ["query 1", "query 2"]}}

Rules:
- Return up to {max_queries - 1} additional queries.
- Do not answer the question.
- Do not invent facts.
- Keep product names, file names, API paths, config keys, and quoted text unchanged when present.
- Favor short search-style queries over full explanations.

Rewrite objectives:
{chr(10).join(active_objectives)}

Conversation summary:
{summary_text}

Recent chat turns:
{context_text}

User question:
{query}
""".strip()


async def build_kb_chat_retrieval_queries(
    query: str,
    *,
    chat_history: list[dict[str, str]] | None = None,
    memory_summary: str | None = None,
    llm_factory: Callable[[], Any] | None = None,
    mode: RewriteMode = "heuristic",
    max_queries: int | None = None,
    strategies: list[str] | None = None,
) -> list[str]:
    """Build retrieval-focused queries for single-round KB chat."""

    original = _normalize_query(query)
    if not original:
        return []

    limit = max(1, min(max_queries or _MAX_RETRIEVAL_QUERIES, _MAX_RETRIEVAL_QUERIES))
    normalized_mode = str(mode or "heuristic").strip().lower()
    strategy_set = {
        str(item).strip()
        for item in list(strategies or [])
        if str(item or "").strip()
    }
    heuristic = _build_heuristic_queries(
        original,
        chat_history=chat_history,
        memory_summary=memory_summary,
        limit=limit,
        strategies=strategy_set,
    )
    if normalized_mode == "skip":
        return [original]
    if normalized_mode != "llm":
        return heuristic or [original]

    try:
        resolved_factory = llm_factory or get_llm_for_analysis
        llm = resolved_factory()
        response = await llm.ainvoke(
            _build_rewrite_prompt(
                original,
                max_queries=limit,
                strategies=strategy_set,
                chat_history=chat_history,
                memory_summary=memory_summary,
            )
        )
        parsed = extract_json_from_llm_response(_coerce_text(getattr(response, "content", response)))
        raw_queries = parsed.get("queries") or []
        llm_queries = [item for item in raw_queries if isinstance(item, str)]
        return _dedupe_keep_order([original, *llm_queries, *heuristic], limit=limit)
    except Exception as exc:
        logger.warning("KB chat query rewrite failed, fallback to heuristic queries: {}", exc)
        return heuristic or [original]
