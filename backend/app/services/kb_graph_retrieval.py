"""Knowledge-graph retrieval helpers for KB chat."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from time import perf_counter
from typing import Any

from loguru import logger

from app.core.config.registry import config_registry
from app.services.graph_store import GraphStore, get_graph_store


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_entities(candidate_entities: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in list(candidate_entities or []):
        value = _clean_text(item)
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


def _resolve_graph_mode(question_type: str | None, graph_mode: str | None) -> str:
    explicit = _clean_text(graph_mode).lower()
    if explicit:
        return explicit
    normalized = _clean_text(question_type).lower()
    if normalized in {
        "summary_lookup",
        "relationship_lookup",
        "relation_lookup",
        "dependency_lookup",
        "call_chain_lookup",
        "comparison_lookup",
        "workflow_lookup",
    }:
        return "relation_evidence"
    return "disabled"


def _build_relation_fact_ref(
    *,
    source_entity_id: str | None,
    relation_type: str | None,
    target_entity_id: str | None,
) -> dict[str, Any] | None:
    source_id = _clean_text(source_entity_id)
    target_id = _clean_text(target_entity_id)
    normalized_relation_type = _clean_text(relation_type)
    if not source_id or not target_id or not normalized_relation_type:
        return None
    return {
        "source_entity_id": source_id,
        "relation_type": normalized_relation_type,
        "target_entity_id": target_id,
    }


def _normalize_relation_fact(row: dict[str, Any], *, rank: int) -> dict[str, Any] | None:
    source_name = _clean_text(row.get("source_name"))
    target_name = _clean_text(row.get("target_name"))
    if not source_name or not target_name:
        return None
    return {
        "rank": rank,
        "source": {
            "entity_id": _clean_text(row.get("source_entity_id")) or None,
            "name": source_name,
            "entity_type": _clean_text(row.get("source_entity_type")) or None,
        },
        "target": {
            "entity_id": _clean_text(row.get("target_entity_id")) or None,
            "name": target_name,
            "entity_type": _clean_text(row.get("target_entity_type")) or None,
        },
        "relation_type": _clean_text(row.get("relation_type") or "RELATED_TO"),
        "evidence": _clean_text(row.get("evidence")) or None,
        "document_id": row.get("document_id"),
        "document_chunk_id": row.get("document_chunk_id"),
        "document_title": _clean_text(row.get("document_title")) or None,
        "section_path": _clean_text(row.get("section_path")) or None,
        "matched_entities": [
            value
            for value in [source_name, target_name]
            if value
        ],
    }


def _build_text_fact_from_relation(relation_fact: dict[str, Any], *, rank: int) -> dict[str, Any]:
    source = dict(relation_fact.get("source") or {})
    target = dict(relation_fact.get("target") or {})
    source_name = _clean_text(source.get("name"))
    target_name = _clean_text(target.get("name"))
    relation_type = _clean_text(relation_fact.get("relation_type") or "RELATED_TO")
    evidence = _clean_text(relation_fact.get("evidence"))
    content = evidence or f"{source_name} -{relation_type}-> {target_name}"
    return {
        "rank": rank,
        "content": content,
        "document_id": relation_fact.get("document_id"),
        "document_chunk_id": relation_fact.get("document_chunk_id"),
        "document_title": relation_fact.get("document_title") or f"{source_name} -> {target_name}",
        "section_path": relation_fact.get("section_path"),
        "relation_type": relation_type,
        "matched_entities": [value for value in [source_name, target_name] if value],
        "evidence": evidence or None,
        "graph_mode": "relation_evidence",
        "fact_ref": _build_relation_fact_ref(
            source_entity_id=source.get("entity_id"),
            relation_type=relation_type,
            target_entity_id=target.get("entity_id"),
        ),
    }


def _normalize_path_fact(row: dict[str, Any], *, rank: int) -> dict[str, Any] | None:
    signature = _clean_text(row.get("signature"))
    matched_entities = [
        _clean_text(item)
        for item in list(row.get("matched_entities") or [])
        if _clean_text(item)
    ]
    if not signature and matched_entities:
        signature = " -> ".join(matched_entities)
    if not signature:
        return None
    return {
        "rank": rank,
        "path_id": _clean_text(row.get("path_id")) or signature,
        "signature": signature,
        "hop_count": int(row.get("hop_count") or 0),
        "content": _clean_text(row.get("content")) or signature,
        "matched_entities": matched_entities,
        "relation_types": [
            _clean_text(item)
            for item in list(row.get("relation_types") or [])
            if _clean_text(item)
        ],
        "evidence": [dict(item) for item in list(row.get("evidence") or []) if isinstance(item, dict)],
    }


def _build_supporting_entities(relation_facts: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}
    for relation in relation_facts:
        for side in ("source", "target"):
            entity = dict(relation.get(side) or {})
            entity_id = _clean_text(entity.get("entity_id")) or f"{side}:{_clean_text(entity.get('name'))}"
            name = _clean_text(entity.get("name"))
            if not name:
                continue
            entities.setdefault(
                entity_id,
                {
                    "entity_id": _clean_text(entity.get("entity_id")) or None,
                    "name": name,
                    "entity_type": _clean_text(entity.get("entity_type")) or None,
                },
            )
            if len(entities) >= limit:
                break
        if len(entities) >= limit:
            break
    return list(entities.values())[:limit]


def _clip_log_text(value: Any, *, limit: int = 220) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _build_relation_evidence_log_items(
    relation_facts: list[dict[str, Any]],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for relation in relation_facts[:limit]:
        source = dict(relation.get("source") or {})
        target = dict(relation.get("target") or {})
        items.append(
            {
                "来源实体": _clean_text(source.get("name")) or None,
                "关系类型": _clean_text(relation.get("relation_type")) or None,
                "目标实体": _clean_text(target.get("name")) or None,
                "证据": _clip_log_text(relation.get("evidence")),
                "文档标题": _clean_text(relation.get("document_title")) or None,
                "分块ID": relation.get("document_chunk_id"),
            }
        )
    return items


def _write_retrieval_log(payload: dict[str, Any]) -> None:
    logger.bind(kb_retrieval_log=True).info(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    )


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
        allowed_document_ids: Sequence[int] | None = None,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        graph_cfg = config_registry.get_graph_config()
        resolved_enabled = graph_cfg.enabled if self._enabled is None else bool(self._enabled)
        entities = _normalize_entities(candidate_entities)
        resolved_graph_mode = _resolve_graph_mode(question_type, graph_mode)
        resolved_relation_pairs = [dict(item) for item in list(relation_pairs or []) if isinstance(item, dict)]
        resolved_relation_queries = [dict(item) for item in list(relation_queries or []) if isinstance(item, dict)]
        base_trace = {
            "graph_used": resolved_enabled,
            "graph_mode": resolved_graph_mode,
            "entity_count": len(entities),
            "relation_pair_count": len(resolved_relation_pairs),
            "relation_query_count": len(resolved_relation_queries),
            "graph_hits": 0,
            "graph_primary_hits": 0,
            "graph_supporting_hits": 0,
            "allowed_document_count": (
                len(list(allowed_document_ids))
                if allowed_document_ids is not None
                else None
            ),
            "max_hops": int(max_hops or 1),
            "empty_reason": None,
            "error": None,
        }
        if not resolved_enabled:
            return {
                "retrieved_docs": [],
                "graph_facts": {"text": [], "entities": [], "relations": [], "paths": [], "evidence": []},
                "trace": {**base_trace, "empty_reason": "disabled", "latency_ms": 0},
            }
        if resolved_graph_mode == "disabled":
            return {
                "retrieved_docs": [],
                "graph_facts": {"text": [], "entities": [], "relations": [], "paths": [], "evidence": []},
                "trace": {**base_trace, "empty_reason": "skipped_for_question_type", "latency_ms": 0},
            }
        if not entities and not resolved_relation_pairs and not resolved_relation_queries:
            return {
                "retrieved_docs": [],
                "graph_facts": {"text": [], "entities": [], "relations": [], "paths": [], "evidence": []},
                "trace": {**base_trace, "empty_reason": "no_entities", "latency_ms": 0},
            }
        if allowed_document_ids is not None and not list(allowed_document_ids):
            return {
                "retrieved_docs": [],
                "graph_facts": {"text": [], "entities": [], "relations": [], "paths": [], "evidence": []},
                "trace": {**base_trace, "empty_reason": "category_scope_empty", "latency_ms": 0},
            }

        try:
            resolved_store = self._store or get_graph_store(require_indexing=False)
            tasks: list[tuple[str, Any]] = []
            if resolved_relation_pairs:
                tasks.append(
                    (
                        "pair_evidence",
                        resolved_store.search_relation_evidence_for_pairs(
                            relation_pairs=resolved_relation_pairs,
                            knowledge_base_id=knowledge_base_id,
                            team_id=team_id,
                            limit=limit,
                            allowed_document_ids=allowed_document_ids,
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
                            allowed_document_ids=allowed_document_ids,
                        ),
                    )
                )
            if not (resolved_relation_pairs or resolved_relation_queries):
                tasks.append(
                    (
                        "evidence",
                        resolved_store.search_related_evidence(
                            entity_names=entities,
                            knowledge_base_id=knowledge_base_id,
                            team_id=team_id,
                            limit=limit,
                            allowed_document_ids=allowed_document_ids,
                        ),
                    )
                )
            if int(max_hops or 1) > 1:
                tasks.append(
                    (
                        "paths",
                        resolved_store.search_relation_paths(
                            entity_names=entities,
                            relation_pairs=resolved_relation_pairs,
                            relation_queries=resolved_relation_queries,
                            knowledge_base_id=knowledge_base_id,
                            team_id=team_id,
                            max_hops=int(max_hops or 1),
                            limit=limit,
                            allowed_document_ids=allowed_document_ids,
                        ),
                    )
                )
            results = await asyncio.gather(*(task for _name, task in tasks), return_exceptions=True)
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

        relation_facts: list[dict[str, Any]] = []
        path_facts: list[dict[str, Any]] = []
        had_errors = False
        first_error: str | None = None
        for (name, _task), result in zip(tasks, results):
            if isinstance(result, Exception):
                had_errors = True
                if first_error is None:
                    first_error = str(result)
                continue
            rows = list(result or [])
            if name == "paths":
                for index, row in enumerate(rows, start=1):
                    if not isinstance(row, dict):
                        continue
                    normalized_path = _normalize_path_fact(dict(row), rank=index)
                    if normalized_path is not None:
                        path_facts.append(normalized_path)
                continue
            for index, row in enumerate(rows, start=1):
                if not isinstance(row, dict):
                    continue
                relation_fact = _normalize_relation_fact(dict(row), rank=index)
                if relation_fact is not None:
                    relation_facts.append(relation_fact)

        deduped_relations: list[dict[str, Any]] = []
        seen_relation_keys: set[tuple[str, str, str, int | None]] = set()
        for relation in relation_facts:
            source = dict(relation.get("source") or {})
            target = dict(relation.get("target") or {})
            key = (
                _clean_text(source.get("entity_id") or source.get("name")),
                _clean_text(relation.get("relation_type")),
                _clean_text(target.get("entity_id") or target.get("name")),
                relation.get("document_chunk_id"),
            )
            if key in seen_relation_keys:
                continue
            deduped_relations.append(relation)
            seen_relation_keys.add(key)

        text_facts = [
            _build_text_fact_from_relation(relation, rank=index)
            for index, relation in enumerate(deduped_relations, start=1)
        ][: max(1, limit)]

        graph_facts = {
            "text": text_facts,
            "entities": _build_supporting_entities(
                deduped_relations,
                limit=max(max(4, limit), len(deduped_relations) * 2),
            ),
            "relations": deduped_relations,
            "paths": path_facts[: max(2, limit)],
            "evidence": [
                {
                    "rank": relation.get("rank"),
                    "document_id": relation.get("document_id"),
                    "document_chunk_id": relation.get("document_chunk_id"),
                    "document_title": relation.get("document_title"),
                    "section_path": relation.get("section_path"),
                    "relation_type": relation.get("relation_type"),
                    "kind": "relation_evidence",
                    "matched_entities": relation.get("matched_entities") or [],
                    "evidence": relation.get("evidence"),
                    "fact_ref": _build_relation_fact_ref(
                        source_entity_id=dict(relation.get("source") or {}).get("entity_id"),
                        relation_type=relation.get("relation_type"),
                        target_entity_id=dict(relation.get("target") or {}).get("entity_id"),
                    ),
                }
                for relation in deduped_relations
                if relation.get("evidence")
            ],
        }
        all_fact_count = sum(len(items) for items in graph_facts.values())
        relation_evidence_log_items = _build_relation_evidence_log_items(deduped_relations)
        _write_retrieval_log(
            {
                "日志类型": "知识库图谱检索",
                "阶段": "图谱检索完成",
                "范围": {
                    "团队ID": team_id,
                    "知识库ID": knowledge_base_id,
                },
                "检索输入": {
                    "图谱模式": resolved_graph_mode,
                    "匹配实体": entities,
                    "关系对条件": resolved_relation_pairs,
                    "关系查询条件": resolved_relation_queries,
                    "最大跳数": int(max_hops or 1),
                    "数量限制": int(limit or 0),
                },
                "检索结果": {
                    "关系数量": len(graph_facts["relations"]),
                    "路径数量": len(graph_facts["paths"]),
                    "证据数量": len(graph_facts["evidence"]),
                    "图谱命中总数": all_fact_count,
                    "空结果原因": None if all_fact_count else ("error" if had_errors else "no_hits"),
                    "错误": first_error,
                },
                "关系证据": {
                    "样例数量": len(relation_evidence_log_items),
                    "总数": len(deduped_relations),
                    "样例": relation_evidence_log_items,
                },
                "性能": {
                    "耗时毫秒": int((perf_counter() - started_at) * 1000),
                },
            }
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
    allowed_document_ids: Sequence[int] | None = None,
) -> dict[str, Any]:
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
        allowed_document_ids=allowed_document_ids,
    )
