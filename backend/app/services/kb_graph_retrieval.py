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


def _normalize_grounded_entities(grounded_entities: list[dict[str, Any]] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in list(grounded_entities or []):
        if not isinstance(item, dict):
            continue
        value = " ".join(str(item.get("normalized_name") or item.get("display_name") or "").split()).strip()
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


def _build_entity_summary_doc(row: dict[str, Any], rank: int) -> dict[str, Any]:
    display_name = str(row.get("display_name") or row.get("normalized_name") or "Graph entity").strip()
    entity_type = str(row.get("entity_type") or "").strip()
    summary = str(row.get("summary") or "").strip()
    mentions = list(row.get("mentions") or [])
    relations = list(row.get("relations") or [])
    if summary:
        content = summary
    else:
        parts = [display_name]
        if entity_type:
            parts[-1] = f"{display_name}（{entity_type}）"
        if mentions:
            mention_texts = [
                f"{item.get('document_title') or 'Unknown'} / {item.get('section_path') or '-'}"
                for item in mentions[:3]
                if isinstance(item, dict) and (item.get("document_title") or item.get("section_path"))
            ]
            if mention_texts:
                parts.append(f"出现于：{'; '.join(mention_texts)}")
        if relations:
            relation_texts = [
                f"{item.get('relation_type') or 'RELATED_TO'} -> {item.get('other') or 'Unknown'}"
                for item in relations[:3]
                if isinstance(item, dict) and (item.get("relation_type") or item.get("other"))
            ]
            if relation_texts:
                parts.append(f"邻接关系：{'; '.join(relation_texts)}")
        content = "\n".join(parts)
    metadata = {
        "source": "graph_summary",
        "rank": rank,
        "normalized_name": row.get("normalized_name"),
        "document_title": row.get("display_name") or display_name,
        "section_path": None,
        "graph_mode": "entity_summary",
        "graph_summary": summary,
        "matched_entities": [display_name] if display_name else [],
    }
    return {"content": content, "metadata": metadata}


def _build_relation_summary_doc(row: dict[str, Any], rank: int) -> dict[str, Any]:
    source_display = str(row.get("source_display_name") or row.get("source_normalized_name") or "Source").strip()
    target_display = str(row.get("target_display_name") or row.get("target_normalized_name") or "Target").strip()
    relation_type = str(row.get("relation_type") or "RELATED_TO").strip()
    summary = str(row.get("summary") or "").strip()
    source_summary = str(row.get("source_summary") or "").strip()
    target_summary = str(row.get("target_summary") or "").strip()
    evidence = str(row.get("evidence") or "").strip()
    content = summary or evidence or f"{source_display} -{relation_type}-> {target_display}"
    if source_summary or target_summary:
        summary_lines = [content]
        if source_summary:
            summary_lines.append(f"Source summary: {source_summary}")
        if target_summary:
            summary_lines.append(f"Target summary: {target_summary}")
        content = "\n".join(summary_lines)
    metadata = {
        "source": "graph_relation_summary",
        "rank": rank,
        "normalized_name": f"{row.get('source_normalized_name')}::{relation_type}::{row.get('target_normalized_name')}",
        "document_title": f"{source_display} -> {target_display}",
        "section_path": None,
        "graph_mode": "relation_evidence",
        "graph_relation_type": relation_type,
        "graph_summary": summary,
        "graph_evidence": evidence,
        "source_summary": source_summary,
        "target_summary": target_summary,
        "matched_entities": [
            name
            for name in [source_display, target_display]
            if name
        ],
    }
    return {"content": content, "metadata": metadata}


def _normalize_graph_row(row: dict[str, Any], rank: int, *, graph_mode: str) -> dict[str, Any]:
    content = str(row.get("chunk_text") or row.get("evidence") or "").strip()
    metadata = {
        "source": "graph",
        "team_id": row.get("team_id"),
        "knowledge_base_id": row.get("knowledge_base_id"),
        "document_id": row.get("document_id"),
        "document_chunk_id": row.get("document_chunk_id"),
        "document_title": row.get("document_title") or "Graph evidence",
        "section_path": row.get("section_path"),
        "rank": rank,
        "graph_mode": graph_mode,
        "graph_relation_type": row.get("relation_type"),
        "graph_evidence": row.get("evidence"),
        "matched_entities": list(row.get("matched_entities") or []),
    }
    if row.get("chunk_index") is not None:
        metadata["chunk_index"] = row.get("chunk_index")
    return {"content": content, "metadata": metadata}


def _doc_key(doc: dict[str, Any]) -> tuple[Any, ...]:
    metadata = dict(doc.get("metadata") or {})
    document_chunk_id = metadata.get("document_chunk_id")
    if document_chunk_id is not None:
        return ("chunk", int(document_chunk_id))
    source = str(metadata.get("source") or "graph").strip()
    graph_mode = str(metadata.get("graph_mode") or "").strip()
    normalized_name = str(metadata.get("normalized_name") or "").strip()
    relation_type = str(metadata.get("graph_relation_type") or "").strip()
    if source == "graph_summary":
        return ("summary", graph_mode, normalized_name)
    if source == "graph_relation_summary":
        return (
            "relation_summary",
            graph_mode,
            normalized_name,
            relation_type,
        )
    if graph_mode:
        return (source, graph_mode, normalized_name, relation_type)
    return (source, normalized_name, relation_type, str(doc.get("content") or "").strip())


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
        grounded_entities: list[dict[str, Any]] | None = None,
        relation_pairs: list[dict[str, Any]] | None = None,
        relation_queries: list[dict[str, Any]] | None = None,
        question_type: str | None = None,
        graph_mode: str | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        """Retrieve graph evidence and return prompt-ready docs plus trace."""

        started_at = perf_counter()
        graph_cfg = config_registry.get_graph_config()
        resolved_enabled = (
            graph_cfg.enabled if self._enabled is None else bool(self._enabled)
        )
        entities = _normalize_grounded_entities(grounded_entities) or _normalize_entities(candidate_entities)
        resolved_relation_pairs = [dict(item) for item in list(relation_pairs or []) if isinstance(item, dict)]
        resolved_relation_queries = [dict(item) for item in list(relation_queries or []) if isinstance(item, dict)]
        resolved_graph_mode = str(graph_mode or "").strip() or _resolve_graph_mode(question_type)
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
                "trace": {**base_trace, "empty_reason": "no_entities", "latency_ms": 0},
            }

        try:
            resolved_store = self._store or get_graph_store(require_indexing=False)
            tasks: list[tuple[str, Any]] = []
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
            if resolved_graph_mode == "neighborhood_summary":
                tasks.append(
                    (
                        "relation_summary",
                        resolved_store.list_relation_summary_contexts(
                            knowledge_base_id=knowledge_base_id,
                            team_id=team_id,
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
                "trace": {
                    **base_trace,
                    "empty_reason": "error",
                    "error": str(exc),
                    "latency_ms": int((perf_counter() - started_at) * 1000),
                },
            }

        docs: list[dict[str, Any]] = []
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
                docs.extend(
                    _build_entity_summary_doc(dict(row), index)
                    for row in rows
                    if isinstance(row, dict)
                )
            elif name == "relation_summary":
                docs.extend(
                    _build_relation_summary_doc(dict(row), index)
                    for row in rows
                    if isinstance(row, dict)
                )
            else:
                docs.extend(
                    _normalize_graph_row(dict(row), index + offset, graph_mode=resolved_graph_mode)
                    for offset, row in enumerate(rows)
                    if isinstance(row, dict)
                )

        docs = [doc for doc in docs if str(doc.get("content") or "").strip()]
        docs = docs[: max(1, limit)]
        logger.info(
            "[KB Graph Retrieval] done | graph_mode={} graph_hits={} empty_reason={} error={} entities={} relation_pairs={} relation_queries={} latency_ms={}",
            resolved_graph_mode,
            len(docs),
            None if docs else ("error" if had_errors else "no_hits"),
            first_error or "-",
            entities,
            resolved_relation_pairs,
            resolved_relation_queries,
            int((perf_counter() - started_at) * 1000),
        )
        return {
            "retrieved_docs": docs,
            "trace": {
                **base_trace,
                "graph_hits": len(docs),
                "empty_reason": None if docs else ("error" if had_errors else "no_hits"),
                "error": first_error,
                "latency_ms": int((perf_counter() - started_at) * 1000),
            },
        }


async def run_kb_graph_retrieval(
    *,
    knowledge_base_id: int,
    team_id: int,
    candidate_entities: list[str] | None = None,
    grounded_entities: list[dict[str, Any]] | None = None,
    relation_pairs: list[dict[str, Any]] | None = None,
    relation_queries: list[dict[str, Any]] | None = None,
    store: GraphStore | None = None,
    enabled: bool | None = None,
    limit: int = 8,
    question_type: str | None = None,
    graph_mode: str | None = None,
) -> dict[str, Any]:
    """Retrieve KB graph evidence through the graph retriever."""

    return await GraphRetriever(store=store, enabled=enabled).retrieve(
        candidate_entities=candidate_entities,
        grounded_entities=grounded_entities,
        relation_pairs=relation_pairs,
        relation_queries=relation_queries,
        knowledge_base_id=knowledge_base_id,
        team_id=team_id,
        question_type=question_type,
        graph_mode=graph_mode,
        limit=limit,
    )
