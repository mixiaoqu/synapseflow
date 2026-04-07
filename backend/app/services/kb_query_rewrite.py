"""Lightweight retrieval query rewrite helpers for single-round KB chat."""

from __future__ import annotations

import re
from typing import Any, Callable

from loguru import logger

from app.core.config.registry import config_registry
from app.core.llm import get_llm_for_analysis
from app.utils import extract_json_from_llm_response

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


def _build_fallback_queries(query: str, *, limit: int) -> list[str]:
    original = _normalize_query(query)
    if not original:
        return []

    compact = _strip_filler_phrases(original)
    code_tokens = _extract_code_tokens(original)
    candidates: list[str] = [original]

    if compact and compact.casefold() != original.casefold():
        candidates.append(compact)

    if code_tokens:
        candidates.append(" ".join(code_tokens[:3]))
        if compact:
            candidates.append(_normalize_query(f"{compact} {' '.join(code_tokens[:2])}"))

    return _dedupe_keep_order(candidates, limit=limit)


def _build_rewrite_prompt(query: str, *, max_queries: int) -> str:
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
- When useful, cover terminology, scenario phrasing, and entity completion.

User question:
{query}
""".strip()


async def build_kb_chat_retrieval_queries(
    query: str,
    *,
    llm_factory: Callable[[], Any] | None = None,
    allow_llm: bool | None = None,
    max_queries: int | None = None,
) -> list[str]:
    """Build 1-4 retrieval-focused queries for single-round KB chat."""

    original = _normalize_query(query)
    if not original:
        return []

    limit = max(1, min(max_queries or _MAX_RETRIEVAL_QUERIES, _MAX_RETRIEVAL_QUERIES))
    fallback = _build_fallback_queries(original, limit=limit)

    should_use_llm = allow_llm if allow_llm is not None else config_registry.llm_configured
    if not should_use_llm and llm_factory is None:
        return fallback

    try:
        resolved_factory = llm_factory or get_llm_for_analysis
        llm = resolved_factory()
        response = await llm.ainvoke(_build_rewrite_prompt(original, max_queries=limit))
        parsed = extract_json_from_llm_response(_coerce_text(getattr(response, "content", response)))
        raw_queries = parsed.get("queries") or []
        llm_queries = [item for item in raw_queries if isinstance(item, str)]
        return _dedupe_keep_order([original, *llm_queries, *fallback], limit=limit)
    except Exception as exc:
        logger.warning("KB chat query rewrite failed, fallback to heuristic queries: {}", exc)
        return fallback
