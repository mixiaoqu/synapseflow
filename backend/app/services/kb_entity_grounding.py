"""Entity grounding helpers for graph retrieval."""

from __future__ import annotations

from typing import Any

from app.services.graph_store import GraphStore, get_graph_store


def _normalize_candidate(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _candidate_key(value: str) -> str:
    return _normalize_candidate(value).casefold()


def _score_grounding_candidate(*, candidate: str, row: dict[str, Any]) -> tuple[int, int]:
    normalized_candidate = _candidate_key(candidate)
    normalized_name = _candidate_key(str(row.get("normalized_name") or ""))
    display_name = _candidate_key(str(row.get("display_name") or ""))
    aliases = [_candidate_key(str(item)) for item in list(row.get("aliases") or []) if str(item).strip()]
    entity_type = str(row.get("entity_type") or "").strip().upper()

    if normalized_name == normalized_candidate:
        return (3, 1 if entity_type == "MODULE" else 0)
    if display_name == normalized_candidate:
        return (2, 1 if entity_type == "MODULE" else 0)
    if normalized_candidate in aliases:
        return (1, 1 if entity_type == "MODULE" else 0)
    return (0, 0)


def _resolve_match_type(*, candidate: str, row: dict[str, Any]) -> str:
    normalized_candidate = _candidate_key(candidate)
    if _candidate_key(str(row.get("normalized_name") or "")) == normalized_candidate:
        return "normalized_name_exact"
    if _candidate_key(str(row.get("display_name") or "")) == normalized_candidate:
        return "display_name_exact"
    aliases = [_candidate_key(str(item)) for item in list(row.get("aliases") or []) if str(item).strip()]
    if normalized_candidate in aliases:
        return "alias_exact"
    return "unknown"


async def ground_graph_entities(
    *,
    candidate_entities: list[str],
    knowledge_base_id: int,
    team_id: int,
    store: GraphStore | None = None,
) -> dict[str, Any]:
    resolved_store = store or get_graph_store(require_indexing=False)
    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for item in candidate_entities:
        normalized = _normalize_candidate(item)
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        normalized_candidates.append(normalized)
        seen.add(key)

    grounded: list[dict[str, Any]] = []
    ungrounded: list[str] = []
    for candidate in normalized_candidates:
        rows = list(
            await resolved_store.lookup_entities_for_grounding(
                knowledge_base_id=knowledge_base_id,
                team_id=team_id,
                candidate=candidate,
            )
        )
        if not rows:
            ungrounded.append(candidate)
            continue

        ranked_rows = sorted(
            (dict(row) for row in rows if isinstance(row, dict)),
            key=lambda row: _score_grounding_candidate(candidate=candidate, row=row),
            reverse=True,
        )
        best_row = ranked_rows[0]
        grounded.append(
            {
                "query_text": candidate,
                "normalized_name": str(best_row.get("normalized_name") or "").strip(),
                "display_name": str(best_row.get("display_name") or "").strip(),
                "entity_type": str(best_row.get("entity_type") or "").strip(),
                "aliases": list(best_row.get("aliases") or []),
                "match_type": _resolve_match_type(candidate=candidate, row=best_row),
            }
        )

    return {
        "grounded_entities": grounded,
        "ungrounded_entities": ungrounded,
        "grounding_trace": {
            "input_count": len(normalized_candidates),
            "grounded_count": len(grounded),
            "ungrounded_count": len(ungrounded),
        },
    }
