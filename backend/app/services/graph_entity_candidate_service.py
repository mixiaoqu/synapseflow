"""Lightweight graph entity candidate resolution for KB retrieval."""

from __future__ import annotations

import re
from typing import Any

from app.services.graph_store import GraphStore, get_graph_store

_CODE_TOKEN_PATTERN = re.compile(
    r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'|《([^》]+)》|([A-Za-z0-9_./:-]{3,})"
)
_RUNTIME_REFERENCE_PATTERN = re.compile(
    r"(当前页面|这个页面|该页面|本页面|当前页|这个页|本页|这里)"
)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_lookup_key(value: Any) -> str:
    return _normalize_text(value).casefold()


def _extract_protected_tokens(query: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for match in _CODE_TOKEN_PATTERN.finditer(query or ""):
        token = next((group for group in match.groups() if group), "")
        cleaned = _normalize_text(token.strip("`\"'"))
        if len(cleaned) < 2:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        tokens.append(cleaned)
        seen.add(key)
    return tokens


def _build_lookup_terms(
    *,
    query: str,
    candidate_entities: list[str] | None,
    lexical_terms: list[str] | None,
    page_context: dict[str, Any] | None,
) -> list[dict[str, str]]:
    terms: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(value: Any, source: str) -> None:
        cleaned = _normalize_text(value)
        if len(cleaned) < 2:
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        terms.append({"text": cleaned, "source": source})

    for item in list(candidate_entities or []):
        add(item, "rewrite_candidate")
    if not terms:
        for item in list(lexical_terms or []):
            add(item, "lexical_term")
    for token in _extract_protected_tokens(query):
        add(token, "protected_token")

    if _RUNTIME_REFERENCE_PATTERN.search(query or "") and isinstance(page_context, dict):
        add(page_context.get("page_name"), "page_context")
        add(page_context.get("page_type"), "page_context")

    return terms


def _score_match(row: dict[str, Any], term: str, source: str) -> tuple[int, str]:
    normalized_term = _normalize_lookup_key(term)
    normalized_name = _normalize_lookup_key(row.get("name"))
    normalized_canonical_name = _normalize_lookup_key(row.get("canonical_name"))
    aliases = {_normalize_lookup_key(item) for item in list(row.get("aliases") or [])}

    match_type = "fuzzy"
    score = 50
    if normalized_name == normalized_term:
        score = 100
        match_type = "name_exact"
    elif normalized_canonical_name == normalized_term:
        score = 98
        match_type = "canonical_exact"
    elif normalized_term in aliases:
        score = 92
        match_type = "alias_exact"
    elif normalized_term in normalized_name:
        score = 78
        match_type = "name_contains"
    elif any(normalized_term in alias for alias in aliases):
        score = 70
        match_type = "alias_contains"

    if source == "rewrite_candidate":
        score += 8
    elif source == "page_context":
        score += 5
    elif source == "protected_token":
        score += 3
    return score, match_type


async def resolve_graph_candidate_entities(
    *,
    knowledge_base_id: int,
    team_id: int,
    query: str,
    candidate_entities: list[str] | None = None,
    lexical_terms: list[str] | None = None,
    page_context: dict[str, Any] | None = None,
    store: GraphStore | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    lookup_terms = _build_lookup_terms(
        query=query,
        candidate_entities=candidate_entities,
        lexical_terms=lexical_terms,
        page_context=page_context,
    )
    if not lookup_terms:
        fallback = [_normalize_text(item) for item in list(candidate_entities or []) if _normalize_text(item)]
        deduped_fallback = list(dict.fromkeys(fallback))[: max(1, limit)]
        return {
            "candidate_entities": deduped_fallback,
            "matched_entities": [],
            "trace": {
                "lookup_terms": [],
                "resolved_entities": deduped_fallback,
                "unmatched_terms": [],
                "match_count": 0,
                "fallback_used": True,
            },
        }

    resolved_store = store or get_graph_store(require_indexing=False)
    matched_rows: dict[str, dict[str, Any]] = {}
    unmatched_terms: list[str] = []

    for term in lookup_terms:
        rows = await resolved_store.lookup_entities_for_grounding(
            knowledge_base_id=knowledge_base_id,
            team_id=team_id,
            candidate=_normalize_lookup_key(term["text"]),
        )
        if not rows:
            unmatched_terms.append(term["text"])
            continue
        for row in rows:
            entity_id = _normalize_text(row.get("entity_id"))
            name = _normalize_text(row.get("name"))
            if not entity_id or not name:
                continue
            score, match_type = _score_match(dict(row), term["text"], term["source"])
            existing = matched_rows.get(entity_id)
            payload = {
                "entity_id": entity_id,
                "name": name,
                "entity_type": _normalize_text(row.get("entity_type")) or "OTHER",
                "canonical_name": _normalize_text(row.get("canonical_name")),
                "aliases": [_normalize_text(item) for item in list(row.get("aliases") or []) if _normalize_text(item)],
                "score": score,
                "match_type": match_type,
                "matched_text": term["text"],
                "matched_source": term["source"],
            }
            if existing is None or int(payload["score"]) > int(existing["score"]):
                matched_rows[entity_id] = payload

    matched_entities = sorted(
        matched_rows.values(),
        key=lambda item: (-int(item["score"]), item["name"], item["entity_id"]),
    )[: max(1, limit)]
    resolved_entities = [str(item["name"]) for item in matched_entities]
    fallback_entities = [_normalize_text(item) for item in list(candidate_entities or []) if _normalize_text(item)]
    fallback_entities = list(dict.fromkeys(fallback_entities))
    final_entities = resolved_entities or fallback_entities[: max(1, limit)]

    return {
        "candidate_entities": final_entities,
        "matched_entities": matched_entities,
        "trace": {
            "lookup_terms": [dict(item) for item in lookup_terms],
            "resolved_entities": final_entities,
            "unmatched_terms": unmatched_terms,
            "match_count": len(matched_entities),
            "fallback_used": not bool(resolved_entities),
        },
    }
