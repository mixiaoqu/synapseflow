"""Knowledge-graph retrieval helpers for KB chat."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from loguru import logger

from app.core.config.registry import config_registry
from app.services.graph_store import GraphStore, get_graph_store


def _normalize_entities(candidate_entities: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in list(candidate_entities or []):
        value = " ".join(str(item or "").split()).strip()
        if len(value) < 2:
            continue
        key = value.casefold()
        if key in seen:
            continue
        out.append(value)
        seen.add(key)
        if len(out) >= 8:
            break
    return out


def _normalize_graph_row(row: dict[str, Any], rank: int) -> dict[str, Any]:
    content = str(row.get("chunk_text") or row.get("evidence") or "").strip()
    metadata = {
        "source": "graph",
        "document_id": row.get("document_id"),
        "document_chunk_id": row.get("document_chunk_id"),
        "document_title": row.get("document_title") or "Graph evidence",
        "section_path": row.get("section_path"),
        "rank": rank,
        "graph_relation_type": row.get("relation_type"),
        "graph_evidence": row.get("evidence"),
        "matched_entities": list(row.get("matched_entities") or []),
    }
    if row.get("chunk_index") is not None:
        metadata["chunk_index"] = row.get("chunk_index")
    return {"content": content, "metadata": metadata}


async def run_kb_graph_retrieval(
    *,
    candidate_entities: list[str] | None,
    store: GraphStore | None = None,
    enabled: bool | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    """Retrieve graph evidence and return prompt-ready docs plus trace."""

    started_at = perf_counter()
    graph_cfg = config_registry.get_graph_config()
    resolved_enabled = graph_cfg.enabled if enabled is None else bool(enabled)
    entities = _normalize_entities(candidate_entities)
    base_trace = {
        "graph_used": resolved_enabled,
        "entity_count": len(entities),
        "graph_hits": 0,
        "empty_reason": None,
        "error": None,
    }
    if not resolved_enabled:
        return {"retrieved_docs": [], "trace": {**base_trace, "empty_reason": "disabled", "latency_ms": 0}}
    if not entities:
        return {"retrieved_docs": [], "trace": {**base_trace, "empty_reason": "no_entities", "latency_ms": 0}}

    try:
        resolved_store = store or get_graph_store(require_indexing=False)
        rows = await resolved_store.search_related_evidence(entity_names=entities, limit=limit)
    except Exception as exc:
        logger.warning("KB graph retrieval failed: {}", exc)
        return {
            "retrieved_docs": [],
            "trace": {
                **base_trace,
                "empty_reason": "error",
                "error": str(exc),
                "latency_ms": int((perf_counter() - started_at) * 1000),
            },
        }

    docs = [
        _normalize_graph_row(dict(row), index + 1)
        for index, row in enumerate(rows)
        if str(row.get("chunk_text") or row.get("evidence") or "").strip()
    ]
    return {
        "retrieved_docs": docs,
        "trace": {
            **base_trace,
            "graph_hits": len(docs),
            "empty_reason": None if docs else "no_hits",
            "latency_ms": int((perf_counter() - started_at) * 1000),
        },
    }
