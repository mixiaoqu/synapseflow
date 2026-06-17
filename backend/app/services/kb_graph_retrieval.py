"""Knowledge-graph retrieval helpers for KB chat."""

from __future__ import annotations

import asyncio
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


def _resolve_graph_mode(question_type: str | None) -> str:
    normalized = str(question_type or "").strip().lower()
    if normalized in {"definition_lookup", "attribute_lookup"}:
        return "entity_summary"
    if normalized == "summary_lookup":
        return "neighborhood_summary"
    return "relation_evidence"


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_mentions(items: list[Any], *, limit: int = 5) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        document_title = _clean_text(item.get("document_title"))
        section_path = _clean_text(item.get("section_path"))
        evidence = _clean_text(item.get("evidence"))
        mention = {
            "document_title": document_title or None,
            "section_path": section_path or None,
            "evidence": evidence or None,
        }
        if mention["document_title"] or mention["section_path"] or mention["evidence"]:
            mentions.append(mention)
        if len(mentions) >= limit:
            break
    return mentions


def _normalize_entity_fact(row: dict[str, Any], *, rank: int) -> dict[str, Any]:
    display_name = _clean_text(row.get("display_name") or row.get("normalized_name") or "Graph entity")
    normalized_name = _clean_text(row.get("normalized_name"))
    entity_type = _clean_text(row.get("entity_type"))
    summary = str(row.get("summary") or "").strip()
    mentions = _normalize_mentions(list(row.get("mentions") or []))
    return {
        "rank": rank,
        "normalized_name": normalized_name or display_name,
        "display_name": display_name,
        "entity_type": entity_type or None,
        "summary": summary or None,
        "mentions": mentions,
    }


def _normalize_relation_summary_fact(row: dict[str, Any], *, rank: int) -> dict[str, Any]:
    source_display = _clean_text(row.get("source_display_name") or row.get("source_normalized_name") or "Source")
    target_display = _clean_text(row.get("target_display_name") or row.get("target_normalized_name") or "Target")
    relation_type = _clean_text(row.get("relation_type") or "RELATED_TO")
    evidence = str(row.get("evidence") or "").strip()
    summary = str(row.get("summary") or "").strip()
    return {
        "rank": rank,
        "source": {
            "normalized_name": _clean_text(row.get("source_normalized_name")) or source_display,
            "display_name": source_display,
            "entity_type": _clean_text(row.get("source_entity_type")) or None,
            "summary": str(row.get("source_summary") or "").strip() or None,
        },
        "target": {
            "normalized_name": _clean_text(row.get("target_normalized_name")) or target_display,
            "display_name": target_display,
            "entity_type": _clean_text(row.get("target_entity_type")) or None,
            "summary": str(row.get("target_summary") or "").strip() or None,
        },
        "relation_type": relation_type,
        "summary": summary or None,
        "evidence": evidence or None,
    }


def _build_relation_fact_ref(
    *,
    source_normalized_name: str | None,
    relation_type: str | None,
    target_normalized_name: str | None,
) -> dict[str, Any] | None:
    source_name = _clean_text(source_normalized_name)
    target_name = _clean_text(target_normalized_name)
    normalized_relation_type = _clean_text(relation_type)
    if not source_name or not target_name or not normalized_relation_type:
        return None
    return {
        "source": source_name,
        "relation_type": normalized_relation_type,
        "target": target_name,
    }


def _relation_fact_ref_key(fact_ref: dict[str, Any] | None) -> tuple[str, str, str] | None:
    if not isinstance(fact_ref, dict):
        return None
    source_name = _clean_text(fact_ref.get("source"))
    relation_type = _clean_text(fact_ref.get("relation_type"))
    target_name = _clean_text(fact_ref.get("target"))
    if not source_name or not relation_type or not target_name:
        return None
    return (source_name, relation_type, target_name)


def _relation_fact_key(fact: dict[str, Any]) -> tuple[str, str, str] | None:
    source = dict(fact.get("source") or {})
    target = dict(fact.get("target") or {})
    return _relation_fact_ref_key(
        _build_relation_fact_ref(
            source_normalized_name=source.get("normalized_name"),
            relation_type=fact.get("relation_type"),
            target_normalized_name=target.get("normalized_name"),
        )
    )


def _matched_entities_relation_key(
    matched_entities: list[Any] | None,
    relation_type: Any,
) -> tuple[str, str, str] | None:
    names = [_clean_text(item) for item in list(matched_entities or []) if _clean_text(item)]
    if len(names) < 2:
        return None
    normalized_relation_type = _clean_text(relation_type)
    if not normalized_relation_type:
        return None
    return (names[0], normalized_relation_type, names[1])


def _build_entity_fact(
    *,
    normalized_name: str | None,
    display_name: str | None,
    entity_type: str | None = None,
    summary: str | None = None,
    rank: int,
) -> dict[str, Any] | None:
    resolved_display_name = _clean_text(display_name or normalized_name)
    resolved_normalized_name = _clean_text(normalized_name or display_name)
    if not resolved_display_name or not resolved_normalized_name:
        return None
    return {
        "rank": rank,
        "normalized_name": resolved_normalized_name,
        "display_name": resolved_display_name,
        "entity_type": _clean_text(entity_type) or None,
        "summary": str(summary or "").strip() or None,
        "mentions": [],
    }


def _normalize_relation_fact(row: dict[str, Any], *, rank: int) -> dict[str, Any] | None:
    matched_entities = [
        _clean_text(item)
        for item in list(row.get("matched_entities") or [])
        if _clean_text(item)
    ]
    source_normalized_name = _clean_text(row.get("source_normalized_name"))
    target_normalized_name = _clean_text(row.get("target_normalized_name"))
    source_display_name = _clean_text(row.get("source_display_name"))
    target_display_name = _clean_text(row.get("target_display_name"))
    if not source_normalized_name and matched_entities:
        source_normalized_name = matched_entities[0]
    if not target_normalized_name and len(matched_entities) >= 2:
        target_normalized_name = matched_entities[1]
    if not source_display_name and matched_entities:
        source_display_name = matched_entities[0]
    if not target_display_name and len(matched_entities) >= 2:
        target_display_name = matched_entities[1]
    if not source_normalized_name or not target_normalized_name:
        return None
    relation_type = _clean_text(row.get("relation_type") or "RELATED_TO")
    evidence = str(row.get("evidence") or "").strip()
    return {
        "rank": rank,
        "source": {
            "normalized_name": source_normalized_name,
            "display_name": source_display_name or source_normalized_name,
            "entity_type": _clean_text(row.get("source_entity_type")) or None,
            "summary": str(row.get("source_summary") or "").strip() or None,
        },
        "target": {
            "normalized_name": target_normalized_name,
            "display_name": target_display_name or target_normalized_name,
            "entity_type": _clean_text(row.get("target_entity_type")) or None,
            "summary": str(row.get("target_summary") or "").strip() or None,
        },
        "relation_type": relation_type,
        "matched_entities": matched_entities,
        "evidence": evidence or None,
        "document_id": row.get("document_id"),
        "document_chunk_id": row.get("document_chunk_id"),
        "document_title": _clean_text(row.get("document_title")) or None,
        "section_path": _clean_text(row.get("section_path")) or None,
        "chunk_index": row.get("chunk_index"),
    }


def _build_text_fact_from_relation(
    relation_fact: dict[str, Any],
    *,
    rank: int,
    document_info: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    source = dict(relation_fact.get("source") or {})
    target = dict(relation_fact.get("target") or {})
    source_display_name = _clean_text(source.get("display_name") or source.get("normalized_name"))
    target_display_name = _clean_text(target.get("display_name") or target.get("normalized_name"))
    relation_type = _clean_text(relation_fact.get("relation_type"))
    content = str(relation_fact.get("summary") or "").strip()
    if not content and source_display_name and relation_type and target_display_name:
        content = f"{source_display_name} {relation_type} {target_display_name}"
    if not content:
        return None
    resolved_document_info = dict(document_info or {})
    fact = {
        "rank": rank,
        "content": content,
        "document_id": resolved_document_info.get("document_id", relation_fact.get("document_id")),
        "document_chunk_id": resolved_document_info.get(
            "document_chunk_id",
            relation_fact.get("document_chunk_id"),
        ),
        "document_title": _clean_text(
            resolved_document_info.get("document_title")
            or relation_fact.get("document_title")
            or f"{source_display_name} -> {target_display_name}"
            or "Graph fact"
        ),
        "section_path": _clean_text(
            resolved_document_info.get("section_path") or relation_fact.get("section_path")
        )
        or None,
        "relation_type": relation_type or None,
        "matched_entities": [name for name in [source_display_name, target_display_name] if name],
        "evidence": str(
            resolved_document_info.get("evidence") or relation_fact.get("evidence") or ""
        ).strip()
        or None,
    }
    if relation_fact.get("chunk_index") is not None:
        fact["chunk_index"] = relation_fact.get("chunk_index")
    return fact


def _build_evidence_fact(
    row: dict[str, Any],
    *,
    rank: int,
    fact_ref: dict[str, Any] | None,
) -> dict[str, Any]:
    matched_entities = [
        _clean_text(item)
        for item in list(row.get("matched_entities") or [])
        if _clean_text(item)
    ]
    return {
        "rank": rank,
        "document_id": row.get("document_id"),
        "document_chunk_id": row.get("document_chunk_id"),
        "document_title": _clean_text(row.get("document_title")) or None,
        "section_path": _clean_text(row.get("section_path")) or None,
        "relation_type": _clean_text(row.get("relation_type")) or None,
        "kind": "relation_evidence",
        "matched_entities": matched_entities,
        "evidence": str(row.get("evidence") or "").strip() or None,
        "fact_ref": fact_ref,
    }


def _merge_entity_facts(
    entity_facts: list[dict[str, Any]],
    *,
    relation_facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = list(entity_facts)
    seen = {
        _clean_text(item.get("normalized_name")): item
        for item in merged
        if isinstance(item, dict) and _clean_text(item.get("normalized_name"))
    }
    next_rank = len(merged) + 1
    for relation_fact in relation_facts:
        if not isinstance(relation_fact, dict):
            continue
        for side in ("source", "target"):
            entity = dict(relation_fact.get(side) or {})
            entity_fact = _build_entity_fact(
                normalized_name=entity.get("normalized_name"),
                display_name=entity.get("display_name"),
                entity_type=entity.get("entity_type"),
                summary=entity.get("summary"),
                rank=next_rank,
            )
            if entity_fact is None:
                continue
            key = _clean_text(entity_fact.get("normalized_name"))
            if key in seen:
                existing = seen[key]
                if not existing.get("summary") and entity_fact.get("summary"):
                    existing["summary"] = entity_fact.get("summary")
                if not existing.get("entity_type") and entity_fact.get("entity_type"):
                    existing["entity_type"] = entity_fact.get("entity_type")
                continue
            merged.append(entity_fact)
            seen[key] = entity_fact
            next_rank += 1
    return merged


def _build_text_facts_from_relations(
    relation_facts: list[dict[str, Any]],
    evidence_facts: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    evidence_by_relation: dict[tuple[str, str, str], dict[str, Any]] = {}
    evidence_by_matched_entities: dict[tuple[str, str, str], dict[str, Any]] = {}
    for evidence_fact in evidence_facts:
        relation_key = _relation_fact_ref_key(dict(evidence_fact.get("fact_ref") or {}))
        if relation_key is None or relation_key in evidence_by_relation:
            matched_key = _matched_entities_relation_key(
                evidence_fact.get("matched_entities"),
                evidence_fact.get("relation_type"),
            )
            if matched_key is not None and matched_key not in evidence_by_matched_entities:
                evidence_by_matched_entities[matched_key] = evidence_fact
            continue
        evidence_by_relation[relation_key] = evidence_fact
        matched_key = _matched_entities_relation_key(
            evidence_fact.get("matched_entities"),
            evidence_fact.get("relation_type"),
        )
        if matched_key is not None and matched_key not in evidence_by_matched_entities:
            evidence_by_matched_entities[matched_key] = evidence_fact
    text_facts: list[dict[str, Any]] = []
    for index, relation_fact in enumerate(relation_facts, start=1):
        relation_key = _relation_fact_key(relation_fact)
        document_info = evidence_by_relation.get(relation_key) if relation_key is not None else None
        if document_info is None:
            matched_key = _matched_entities_relation_key(
                [
                    dict(relation_fact.get("source") or {}).get("display_name"),
                    dict(relation_fact.get("target") or {}).get("display_name"),
                ],
                relation_fact.get("relation_type"),
            )
            if matched_key is not None:
                document_info = evidence_by_matched_entities.get(matched_key)
        text_fact = _build_text_fact_from_relation(
            relation_fact,
            rank=index,
            document_info=document_info,
        )
        if text_fact is not None:
            text_facts.append(text_fact)
        if len(text_facts) >= limit:
            break
    return text_facts


def _normalize_path_fact(row: dict[str, Any], *, rank: int) -> dict[str, Any] | None:
    signature = _clean_text(row.get("signature"))
    content = str(row.get("content") or "").strip()
    matched_entities = [
        _clean_text(item)
        for item in list(row.get("matched_entities") or [])
        if _clean_text(item)
    ]
    relation_types = [
        _clean_text(item)
        for item in list(row.get("relation_types") or [])
        if _clean_text(item)
    ]
    evidence_rows = [dict(item) for item in list(row.get("evidence") or []) if isinstance(item, dict)]
    if not signature and matched_entities:
        signature = " -> ".join(matched_entities)
    if not content and signature:
        content = signature
    if not signature and not content:
        return None
    return {
        "rank": rank,
        "path_id": _clean_text(row.get("path_id")) or signature,
        "signature": signature or content,
        "hop_count": int(row.get("hop_count") or max(0, len(relation_types))),
        "content": content or signature,
        "matched_entities": matched_entities,
        "relation_types": relation_types,
        "evidence": evidence_rows,
    }


def _build_text_facts_from_paths(path_facts: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    text_facts: list[dict[str, Any]] = []
    for index, path_fact in enumerate(path_facts, start=1):
        content = str(path_fact.get("content") or "").strip()
        signature = _clean_text(path_fact.get("signature"))
        document_info = next(
            (dict(item) for item in list(path_fact.get("evidence") or []) if isinstance(item, dict)),
            {},
        )
        if not content and not signature:
            continue
        text_facts.append(
            {
                "rank": index,
                "content": content or signature,
                "document_id": document_info.get("document_id"),
                "document_chunk_id": document_info.get("document_chunk_id"),
                "document_title": _clean_text(document_info.get("document_title"))
                or f"Graph path #{index}",
                "section_path": _clean_text(document_info.get("section_path")) or None,
                "relation_type": "PATH",
                "matched_entities": list(path_fact.get("matched_entities") or []),
                "evidence": signature or None,
                "path_id": path_fact.get("path_id"),
                "path_signature": signature or None,
            }
        )
        if len(text_facts) >= limit:
            break
    return text_facts


def _align_evidence_fact_refs(
    evidence_facts: list[dict[str, Any]],
    relation_facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    relation_refs_by_matched_entities: dict[tuple[str, str, str], dict[str, Any]] = {}
    for relation_fact in relation_facts:
        source = dict(relation_fact.get("source") or {})
        target = dict(relation_fact.get("target") or {})
        matched_key = _matched_entities_relation_key(
            [source.get("display_name"), target.get("display_name")],
            relation_fact.get("relation_type"),
        )
        relation_ref = _build_relation_fact_ref(
            source_normalized_name=source.get("normalized_name"),
            relation_type=relation_fact.get("relation_type"),
            target_normalized_name=target.get("normalized_name"),
        )
        if matched_key is None or relation_ref is None:
            continue
        relation_refs_by_matched_entities[matched_key] = relation_ref

    aligned_facts: list[dict[str, Any]] = []
    for evidence_fact in evidence_facts:
        matched_key = _matched_entities_relation_key(
            evidence_fact.get("matched_entities"),
            evidence_fact.get("relation_type"),
        )
        if matched_key is None:
            aligned_facts.append(evidence_fact)
            continue
        relation_ref = relation_refs_by_matched_entities.get(matched_key)
        if relation_ref is None:
            aligned_facts.append(evidence_fact)
            continue
        aligned_facts.append({**evidence_fact, "fact_ref": relation_ref})
    return aligned_facts


def _fact_key(fact: dict[str, Any], *, category: str) -> tuple[Any, ...]:
    if category == "text":
        document_chunk_id = fact.get("document_chunk_id")
        if document_chunk_id is not None:
            return ("text", int(document_chunk_id))
        return (
            "text",
            _clean_text(fact.get("document_title")),
            _clean_text(fact.get("section_path")),
            str(fact.get("content") or "").strip(),
        )
    if category == "entities":
        return ("entity", _clean_text(fact.get("normalized_name")))
    if category == "relations":
        source = fact.get("source") if isinstance(fact.get("source"), dict) else {}
        target = fact.get("target") if isinstance(fact.get("target"), dict) else {}
        return (
            "relation",
            _clean_text(source.get("normalized_name")),
            _clean_text(fact.get("relation_type")),
            _clean_text(target.get("normalized_name")),
            _clean_text(fact.get("document_chunk_id")),
        )
    if category == "evidence":
        fact_ref_key = _relation_fact_ref_key(dict(fact.get("fact_ref") or {}))
        return (
            "evidence",
            _clean_text(fact.get("document_chunk_id")),
            _clean_text(fact.get("relation_type")),
            _clean_text(fact.get("evidence")),
            fact_ref_key or (),
        )
    if category == "paths":
        return (
            "path",
            str(fact.get("path_id") or "").strip(),
            str(fact.get("signature") or "").strip(),
        )
    return (category, str(fact).strip())


def _dedupe_facts(items: list[dict[str, Any]], *, category: str, limit: int) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in items:
        key = _fact_key(item, category=category)
        if key in seen:
            continue
        deduped.append(item)
        seen.add(key)
        if len(deduped) >= limit:
            break
    return deduped


class GraphRetriever:
    """Retrieve graph evidence independently from text retrieval."""

    def __init__(
        self,
        *,
        store: GraphStore | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._store = store
        self._enabled = enabled

    async def retrieve(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        candidate_entities: list[str] | None = None,
        relation_pairs: list[dict[str, Any]] | None = None,
        relation_queries: list[dict[str, Any]] | None = None,
        question_type: str | None = None,
        graph_mode: str | None = None,
        max_hops: int = 1,
        limit: int = 8,
    ) -> dict[str, Any]:
        """Retrieve graph facts and return structured graph evidence plus trace."""

        started_at = perf_counter()
        graph_cfg = config_registry.get_graph_config()
        resolved_enabled = (
            graph_cfg.enabled if self._enabled is None else bool(self._enabled)
        )
        entities = _normalize_entities(candidate_entities)
        resolved_graph_mode = str(graph_mode or "").strip() or _resolve_graph_mode(question_type)
        resolved_relation_pairs = [dict(item) for item in list(relation_pairs or []) if isinstance(item, dict)]
        resolved_relation_queries = [dict(item) for item in list(relation_queries or []) if isinstance(item, dict)]
        logger.info(
            "[KB Graph Retrieval] start | kb_id={} team_id={} question_type={} graph_mode={} enabled={} entities={} relation_pairs={} relation_queries={} limit={}",
            knowledge_base_id,
            team_id,
            question_type or "-",
            resolved_graph_mode,
            resolved_enabled,
            entities,
            len(resolved_relation_pairs),
            len(resolved_relation_queries),
            limit,
        )
        base_trace = {
            "graph_used": resolved_enabled,
            "graph_mode": resolved_graph_mode,
            "entity_count": len(entities),
            "relation_pair_count": len(resolved_relation_pairs),
            "relation_query_count": len(resolved_relation_queries),
            "graph_hits": 0,
            "graph_primary_hits": 0,
            "graph_supporting_hits": 0,
            "max_hops": int(max_hops or 1),
            "empty_reason": None,
            "error": None,
        }
        if not resolved_enabled:
            logger.info(
                "[KB Graph Retrieval] skip | reason=disabled graph_mode={} entities={} relation_pairs={} relation_queries={}",
                resolved_graph_mode,
                entities,
                resolved_relation_pairs,
                resolved_relation_queries,
            )
            return {
                "retrieved_docs": [],
                "graph_facts": {"text": [], "entities": [], "relations": [], "paths": [], "evidence": []},
                "trace": {**base_trace, "empty_reason": "disabled", "latency_ms": 0},
            }
        if not entities and not resolved_relation_pairs and not resolved_relation_queries:
            logger.info(
                "[KB Graph Retrieval] skip | reason=no_entities graph_mode={} entities={} relation_pairs={} relation_queries={}",
                resolved_graph_mode,
                entities,
                resolved_relation_pairs,
                resolved_relation_queries,
            )
            return {
                "retrieved_docs": [],
                "graph_facts": {"text": [], "entities": [], "relations": [], "paths": [], "evidence": []},
                "trace": {**base_trace, "empty_reason": "no_entities", "latency_ms": 0},
            }

        try:
            resolved_store = self._store or get_graph_store(require_indexing=False)
            tasks: list[tuple[str, Any]] = []
            path_search = getattr(resolved_store, "search_relation_paths", None)
            if resolved_graph_mode in {"entity_summary", "neighborhood_summary"}:
                tasks.append(
                    (
                        "entity_summary",
                        resolved_store.list_entity_summary_contexts(
                            knowledge_base_id=knowledge_base_id,
                            team_id=team_id,
                            normalized_names=entities,
                        ),
                    )
                )
            if resolved_graph_mode in {"relation_evidence", "neighborhood_summary"} and not (
                resolved_relation_pairs or resolved_relation_queries
            ):
                tasks.append(
                    (
                        "relation_summary",
                        resolved_store.list_relation_summary_contexts(
                            knowledge_base_id=knowledge_base_id,
                            team_id=team_id,
                            normalized_names=entities,
                        ),
                    )
                )
            if resolved_graph_mode in {"relation_evidence", "neighborhood_summary"}:
                if resolved_relation_pairs:
                    tasks.append(
                        (
                            "pair_evidence",
                            resolved_store.search_relation_evidence_for_pairs(
                                relation_pairs=resolved_relation_pairs,
                                knowledge_base_id=knowledge_base_id,
                                team_id=team_id,
                                limit=limit,
                            ),
                        )
                    )
                if resolved_relation_queries:
                    tasks.append(
                        (
                            "query_evidence",
                            resolved_store.search_relation_evidence_for_queries(
                                relation_queries=resolved_relation_queries,
                                knowledge_base_id=knowledge_base_id,
                                team_id=team_id,
                                limit=limit,
                            ),
                        )
                    )
            if resolved_graph_mode in {"relation_evidence", "neighborhood_summary"} and not (
                resolved_relation_pairs or resolved_relation_queries
            ):
                tasks.append(
                    (
                        "evidence",
                        resolved_store.search_related_evidence(
                            entity_names=entities,
                            knowledge_base_id=knowledge_base_id,
                            team_id=team_id,
                            limit=limit,
                        ),
                    )
                )
            if (
                callable(path_search)
                and resolved_graph_mode in {"relation_evidence", "neighborhood_summary"}
                and int(max_hops or 1) > 1
            ):
                tasks.append(
                    (
                        "paths",
                        path_search(
                            entity_names=entities,
                            relation_pairs=resolved_relation_pairs,
                            relation_queries=resolved_relation_queries,
                            knowledge_base_id=knowledge_base_id,
                            team_id=team_id,
                            max_hops=int(max_hops or 1),
                            limit=limit,
                        ),
                    )
                )
            logger.debug(
                "[KB Graph Retrieval] scheduled subtasks | mode={} task_count={} task_names={}",
                resolved_graph_mode,
                len(tasks),
                [name for name, _task in tasks],
            )
            if not tasks:
                tasks.append(
                    (
                        "evidence",
                        resolved_store.search_related_evidence(
                            entity_names=entities,
                            knowledge_base_id=knowledge_base_id,
                            team_id=team_id,
                            limit=limit,
                        ),
                    )
                )
            logger.debug(
                "[KB Graph Retrieval] executing subtasks | mode={} task_names={}",
                resolved_graph_mode,
                [name for name, _task in tasks],
            )

            results = await asyncio.gather(
                *(task for _name, task in tasks),
                return_exceptions=True,
            )
        except Exception as exc:
            logger.warning("KB graph retrieval failed: {}", exc)
            return {
                "retrieved_docs": [],
                "graph_facts": {"text": [], "entities": [], "relations": [], "paths": [], "evidence": []},
                "trace": {
                    **base_trace,
                    "empty_reason": "error",
                    "error": str(exc),
                    "latency_ms": int((perf_counter() - started_at) * 1000),
                },
            }

        entity_facts: list[dict[str, Any]] = []
        relation_facts: list[dict[str, Any]] = []
        path_facts: list[dict[str, Any]] = []
        evidence_facts: list[dict[str, Any]] = []
        had_errors = False
        first_error: str | None = None
        for index, ((name, _task), result) in enumerate(zip(tasks, results), start=1):
            if isinstance(result, Exception):
                logger.warning("KB graph retrieval subtask failed mode={}: {}", name, result)
                had_errors = True
                if first_error is None:
                    first_error = str(result)
                continue
            rows = list(result or [])
            logger.debug(
                "[KB Graph Retrieval] subtask result | mode={} rows={}",
                name,
                len(rows),
            )
            if name == "entity_summary":
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    normalized_row = dict(row)
                    entity_facts.append(_normalize_entity_fact(normalized_row, rank=index))
                    relation_rows = list(normalized_row.get("relations") or [])
                    for offset, relation_row in enumerate(relation_rows, start=1):
                        if not isinstance(relation_row, dict):
                            continue
                        relation_type = _clean_text(relation_row.get("relation_type") or "RELATED_TO")
                        other_name = _clean_text(relation_row.get("other") or "Unknown")
                        relation_facts.append(
                            {
                                "rank": index + offset,
                                "source": {
                                    "normalized_name": _clean_text(normalized_row.get("normalized_name"))
                                    or _clean_text(normalized_row.get("display_name")),
                                    "display_name": _clean_text(normalized_row.get("display_name"))
                                    or _clean_text(normalized_row.get("normalized_name")),
                                    "entity_type": _clean_text(normalized_row.get("entity_type")) or None,
                                    "summary": str(normalized_row.get("summary") or "").strip() or None,
                                },
                                "target": {
                                    "normalized_name": other_name,
                                    "display_name": other_name,
                                    "entity_type": None,
                                    "summary": None,
                                },
                                "relation_type": relation_type,
                                "summary": None,
                                "evidence": str(relation_row.get("evidence") or "").strip() or None,
                            }
                        )
                    mention_rows = list(normalized_row.get("mentions") or [])
                    for offset, mention_row in enumerate(mention_rows, start=1):
                        if not isinstance(mention_row, dict):
                            continue
                        evidence_facts.append(
                            {
                                "rank": index + offset,
                                "kind": "entity_mention",
                                "document_title": _clean_text(mention_row.get("document_title")) or None,
                                "section_path": _clean_text(mention_row.get("section_path")) or None,
                                "evidence": str(mention_row.get("evidence") or "").strip() or None,
                                "matched_entities": [
                                    _clean_text(normalized_row.get("display_name"))
                                    or _clean_text(normalized_row.get("normalized_name"))
                                ],
                            }
                        )
            elif name == "relation_summary":
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    relation_fact = _normalize_relation_summary_fact(dict(row), rank=index)
                    relation_facts.append(relation_fact)
            elif name == "paths":
                for offset, row in enumerate(rows, start=1):
                    if not isinstance(row, dict):
                        continue
                    path_fact = _normalize_path_fact(dict(row), rank=index + offset)
                    if path_fact is not None:
                        path_facts.append(path_fact)
            else:
                for offset, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    normalized_row = dict(row)
                    relation_fact: dict[str, Any] | None = None
                    if name in {"pair_evidence", "query_evidence"}:
                        relation_fact = _normalize_relation_fact(
                            normalized_row,
                            rank=index + offset,
                        )
                        if relation_fact is not None:
                            relation_facts.append(relation_fact)
                    elif name == "evidence":
                        relation_fact = _normalize_relation_fact(
                            normalized_row,
                            rank=index + offset,
                        )
                    fact_ref = None
                    if relation_fact is not None:
                        fact_ref = _build_relation_fact_ref(
                            source_normalized_name=dict(relation_fact.get("source") or {}).get(
                                "normalized_name"
                            ),
                            relation_type=relation_fact.get("relation_type"),
                            target_normalized_name=dict(relation_fact.get("target") or {}).get(
                                "normalized_name"
                            ),
                        )
                    evidence_facts.append(
                        _build_evidence_fact(
                            normalized_row,
                            rank=index + offset,
                            fact_ref=fact_ref,
                        )
                    )

        deduped_relations = _dedupe_facts(
            relation_facts,
            category="relations",
            limit=max(4, limit * 2),
        )
        merged_entities = _merge_entity_facts(entity_facts, relation_facts=deduped_relations)
        deduped_entities = _dedupe_facts(merged_entities, category="entities", limit=max(4, limit))
        aligned_evidence = _align_evidence_fact_refs(evidence_facts, deduped_relations)
        deduped_evidence = _dedupe_facts(
            aligned_evidence,
            category="evidence",
            limit=max(4, limit * 2),
        )
        text_facts = _build_text_facts_from_relations(
            deduped_relations,
            deduped_evidence,
            limit=max(1, limit),
        )
        text_facts.extend(
            _build_text_facts_from_paths(
                _dedupe_facts(path_facts, category="paths", limit=max(2, limit)),
                limit=max(1, limit),
            )
        )
        graph_facts = {
            "text": _dedupe_facts(text_facts, category="text", limit=max(1, limit)),
            "entities": deduped_entities,
            "relations": deduped_relations,
            "paths": _dedupe_facts(path_facts, category="paths", limit=max(2, limit)),
            "evidence": deduped_evidence,
        }
        all_fact_count = sum(len(items) for items in graph_facts.values())
        logger.info(
            "[KB Graph Retrieval] done | graph_mode={} text_count={} entity_count={} relation_count={} path_count={} evidence_count={} graph_hits={} empty_reason={} error={} entities={} relation_pairs={} relation_queries={} latency_ms={}",
            resolved_graph_mode,
            len(graph_facts["text"]),
            len(graph_facts["entities"]),
            len(graph_facts["relations"]),
            len(graph_facts["paths"]),
            len(graph_facts["evidence"]),
            all_fact_count,
            None if all_fact_count else ("error" if had_errors else "no_hits"),
            first_error or "-",
            entities,
            resolved_relation_pairs,
            resolved_relation_queries,
            int((perf_counter() - started_at) * 1000),
        )
        return {
            "retrieved_docs": graph_facts["text"],
            "graph_facts": graph_facts,
            "trace": {
                **base_trace,
                "graph_hits": all_fact_count,
                "graph_primary_hits": len(graph_facts["text"]),
                "graph_supporting_hits": len(graph_facts["entities"]) + len(graph_facts["relations"]) + len(graph_facts["evidence"]) + len(graph_facts["paths"]),
                "empty_reason": None if all_fact_count else ("error" if had_errors else "no_hits"),
                "error": first_error,
                "latency_ms": int((perf_counter() - started_at) * 1000),
            },
        }


async def run_kb_graph_retrieval(
    *,
    knowledge_base_id: int,
    team_id: int,
    candidate_entities: list[str] | None = None,
    relation_pairs: list[dict[str, Any]] | None = None,
    relation_queries: list[dict[str, Any]] | None = None,
    store: GraphStore | None = None,
    enabled: bool | None = None,
    limit: int = 8,
    question_type: str | None = None,
    graph_mode: str | None = None,
    max_hops: int = 1,
) -> dict[str, Any]:
    """Retrieve KB graph evidence through the graph retriever."""

    return await GraphRetriever(store=store, enabled=enabled).retrieve(
        candidate_entities=candidate_entities,
        relation_pairs=relation_pairs,
        relation_queries=relation_queries,
        knowledge_base_id=knowledge_base_id,
        team_id=team_id,
        question_type=question_type,
        graph_mode=graph_mode,
        max_hops=max_hops,
        limit=limit,
    )
