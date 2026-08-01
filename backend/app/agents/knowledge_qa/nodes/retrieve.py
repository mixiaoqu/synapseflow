"""Text and graph retrieval node for knowledge-base chat."""

from __future__ import annotations

import asyncio
import hashlib
import json
from time import perf_counter
from typing import Any, Callable

import httpx
from loguru import logger

from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.knowledge_qa.evidence_coverage import assess_subtask_coverage
from app.agents.knowledge_qa.state import KnowledgeQaState
from app.core.config.registry import config_registry
from app.core.config.settings import settings
from app.services.kb_text_retrieval import run_kb_channel_text_retrieval
from app.services.reranker import rerank

FINAL_RERANK_CANDIDATE_MULTIPLIER = 3
FINAL_RERANK_TEXT_MAX_CHARS = 1200
FINAL_RERANK_CONTEXT_MAX_CHARS = 600
GRAPH_RERANK_SOURCE_PREFIX = "graph"
TEXT_GRAPH_RERANK_SOURCE = "text_graph"


def _doc_key(doc: dict[str, Any]) -> tuple[Any, ...]:
    metadata = dict(doc.get("metadata") or {})
    document_chunk_id = metadata.get("document_chunk_id")
    if document_chunk_id is not None:
        return ("chunk", int(document_chunk_id))
    source = str(metadata.get("source") or "graph").strip()
    graph_mode = str(metadata.get("graph_mode") or "").strip()
    graph_key = str(metadata.get("graph_key") or "").strip()
    relation_type = str(metadata.get("graph_relation_type") or "").strip()
    return (source, graph_mode, graph_key, relation_type, str(doc.get("content") or "").strip())


def _build_graph_text_doc(fact: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "source": "graph",
        "document_id": fact.get("document_id"),
        "document_chunk_id": fact.get("document_chunk_id"),
        "document_title": fact.get("document_title") or "Graph evidence",
        "section_path": fact.get("section_path"),
        "graph_mode": fact.get("graph_mode"),
        "graph_relation_type": fact.get("relation_type"),
        "graph_evidence": fact.get("evidence"),
        "matched_entities": list(fact.get("matched_entities") or []),
        "rank": fact.get("rank"),
    }
    if fact.get("chunk_index") is not None:
        metadata["chunk_index"] = fact.get("chunk_index")
    return {"content": str(fact.get("content") or "").strip(), "metadata": metadata}


def _build_entity_fact_doc(fact: dict[str, Any], *, index: int) -> dict[str, Any] | None:
    display_name = str(fact.get("name") or f"Entity {index}").strip()
    entity_type = str(fact.get("entity_type") or "").strip()
    lines = [display_name]
    if entity_type:
        lines[0] = f"{lines[0]}（{entity_type}）" if lines[0] == display_name else lines[0]
    content = "\n".join(line for line in lines if line).strip()
    if not content:
        return None

    return {
        "content": content,
        "metadata": {
            "source": "graph_entity",
            "rank": fact.get("rank", index),
            "graph_key": fact.get("entity_id") or display_name,
            "document_title": display_name,
            "section_path": None,
            "graph_mode": "relation_evidence",
            "matched_entities": [display_name] if display_name else [],
            "supporting_section": "实体",
        },
    }


def _build_relation_fact_doc(fact: dict[str, Any], *, index: int) -> dict[str, Any] | None:
    source = dict(fact.get("source") or {})
    target = dict(fact.get("target") or {})
    source_display = str(source.get("name") or "Source").strip()
    target_display = str(target.get("name") or "Target").strip()
    relation_type = str(fact.get("relation_type") or "RELATED_TO").strip()
    evidence = str(fact.get("evidence") or "").strip()

    lines = [evidence or f"{source_display} -{relation_type}-> {target_display}"]
    content = "\n".join(line for line in lines if line).strip()
    if not content:
        return None

    return {
        "content": content,
        "metadata": {
            "source": "graph_relation",
            "rank": fact.get("rank", index),
            "graph_key": f"{source.get('entity_id') or source_display}::{relation_type}::{target.get('entity_id') or target_display}",
            "document_id": fact.get("document_id"),
            "document_chunk_id": fact.get("document_chunk_id"),
            "document_title": fact.get("document_title") or f"{source_display} -> {target_display}",
            "section_path": fact.get("section_path"),
            "graph_mode": "relation_evidence",
            "graph_relation_type": relation_type,
            "graph_evidence": evidence or None,
            "matched_entities": [name for name in [source_display, target_display] if name],
            "supporting_section": "关系",
        },
    }


def _build_evidence_fact_doc(fact: dict[str, Any], *, index: int) -> dict[str, Any] | None:
    evidence = str(fact.get("evidence") or "").strip()
    document_title = str(fact.get("document_title") or "关联证据").strip()
    section_path = str(fact.get("section_path") or "").strip()
    matched_entities = [
        str(item).strip()
        for item in list(fact.get("matched_entities") or [])
        if str(item or "").strip()
    ]

    lines = [evidence] if evidence else []
    if section_path:
        lines.append(f"位置：{section_path}")
    content = "\n".join(line for line in lines if line).strip()
    if not content:
        return None

    return {
        "content": content,
        "metadata": {
            "source": "graph_relation_evidence",
            "rank": fact.get("rank", index),
            "graph_key": str(fact.get("document_chunk_id") or document_title),
            "document_id": fact.get("document_id"),
            "document_chunk_id": fact.get("document_chunk_id"),
            "document_title": document_title,
            "section_path": section_path or None,
            "graph_mode": "relation_evidence",
            "graph_evidence": evidence or None,
            "graph_relation_type": fact.get("relation_type"),
            "matched_entities": matched_entities,
            "supporting_section": "关系证据",
        },
    }


def _build_path_fact_doc(fact: dict[str, Any], *, index: int) -> dict[str, Any] | None:
    signature = str(fact.get("signature") or "").strip()
    content = str(fact.get("content") or "").strip()
    hop_count = int(fact.get("hop_count") or 0)
    evidence_rows = [dict(item) for item in list(fact.get("evidence") or []) if isinstance(item, dict)]
    lines = [content or signature]
    if signature and signature != lines[0]:
        lines.append(f"路径：{signature}")
    if hop_count > 0:
        lines.append(f"跳数：{hop_count}")
    if evidence_rows:
        lines.extend(
            [
                f"{str(item.get('relation_type') or 'RELATED_TO').strip()}：{str(item.get('evidence') or '').strip()}"
                for item in evidence_rows[:3]
                if str(item.get("evidence") or "").strip()
            ]
        )
    rendered = "\n".join(line for line in lines if line).strip()
    if not rendered:
        return None
    return {
        "content": rendered,
        "metadata": {
            "source": "graph_path",
            "rank": fact.get("rank", index),
            "graph_key": str(fact.get("path_id") or signature or index),
            "document_title": f"多跳路径 {index}",
            "section_path": None,
            "graph_mode": "relation_evidence",
            "graph_evidence": signature or None,
            "matched_entities": list(fact.get("matched_entities") or []),
            "supporting_section": "路径",
        },
    }


def _build_graph_docs_from_facts(graph_facts: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    primary_docs = [
        _build_graph_text_doc(fact)
        for fact in list(graph_facts.get("text") or [])
        if isinstance(fact, dict) and str(fact.get("content") or "").strip()
    ]
    supporting_docs: list[dict[str, Any]] = []
    for index, fact in enumerate(list(graph_facts.get("entities") or []), start=1):
        if not isinstance(fact, dict):
            continue
        doc = _build_entity_fact_doc(fact, index=index)
        if doc is not None:
            supporting_docs.append(doc)
    for index, fact in enumerate(list(graph_facts.get("relations") or []), start=1):
        if not isinstance(fact, dict):
            continue
        doc = _build_relation_fact_doc(fact, index=index)
        if doc is not None:
            supporting_docs.append(doc)
    for index, fact in enumerate(list(graph_facts.get("evidence") or []), start=1):
        if not isinstance(fact, dict):
            continue
        doc = _build_evidence_fact_doc(fact, index=index)
        if doc is not None:
            supporting_docs.append(doc)
    for index, fact in enumerate(list(graph_facts.get("paths") or []), start=1):
        if not isinstance(fact, dict):
            continue
        doc = _build_path_fact_doc(fact, index=index)
        if doc is not None:
            supporting_docs.append(doc)
    return primary_docs, supporting_docs


def _merge_text_and_graph_docs(
    text_docs: list[dict[str, Any]],
    graph_docs: list[dict[str, Any]],
    *,
    final_top_k: int,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    graph_by_key = {_doc_key(doc): doc for doc in graph_docs}
    used_graph_keys: set[tuple[Any, ...]] = set()

    for doc in text_docs:
        key = _doc_key(doc)
        graph_doc = graph_by_key.get(key)
        if graph_doc:
            metadata = {**dict(doc.get("metadata") or {})}
            graph_metadata = dict(graph_doc.get("metadata") or {})
            metadata["graph_evidence"] = graph_metadata.get("graph_evidence")
            metadata["graph_relation_type"] = graph_metadata.get("graph_relation_type")
            metadata["matched_entities"] = graph_metadata.get("matched_entities") or []
            metadata["source"] = "text_graph"
            merged.append({"content": doc.get("content") or "", "metadata": metadata})
            used_graph_keys.add(key)
        else:
            merged.append(doc)

    for doc in graph_docs:
        key = _doc_key(doc)
        if key in used_graph_keys:
            continue
        merged.append(doc)
        if len(merged) >= final_top_k:
            break
    return merged[:final_top_k]


def _dedupe_terms(items: list[str]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for item in items:
        for value in str(item or "").split():
            normalized = value.strip()
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            terms.append(normalized)
            seen.add(key)
    return terms


def _dedupe_queries(items: list[str]) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = " ".join(str(item or "").split()).strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        queries.append(value)
        seen.add(key)
    return queries


def _normalized_rerank_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _rerank_evidence_texts(metadata: dict[str, Any]) -> list[str]:
    additional_values = metadata.get("evidence_texts")
    if not isinstance(additional_values, list):
        additional_values = []
    values = [
        metadata.get("evidence_text"),
        *additional_values,
    ]
    evidence_texts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _normalized_rerank_text(value)
        key = text.casefold()
        if not text or key in seen:
            continue
        evidence_texts.append(text)
        seen.add(key)
    return evidence_texts


def _centered_rerank_context(
    content: str,
    *,
    evidence_texts: list[str],
    limit: int = FINAL_RERANK_CONTEXT_MAX_CHARS,
) -> str:
    normalized_content = _normalized_rerank_text(content)
    if not normalized_content or limit <= 0:
        return ""
    if len(normalized_content) <= limit:
        return normalized_content

    matched_evidence: list[tuple[int, str]] = []
    for evidence_text in evidence_texts:
        position = normalized_content.find(evidence_text)
        if position >= 0:
            matched_evidence.append((position, evidence_text))
    if not matched_evidence:
        return normalized_content[:limit]

    anchor_start, anchor_text = min(matched_evidence, key=lambda item: item[0])
    anchor_center = anchor_start + len(anchor_text) // 2
    start = max(0, anchor_center - limit // 2)
    end = min(len(normalized_content), start + limit)
    start = max(0, end - limit)
    return normalized_content[start:end]


def _build_rerank_text(doc: dict[str, Any]) -> str:
    metadata = dict(doc.get("metadata") or {})
    title = str(metadata.get("document_title") or "").strip()
    section_path = str(metadata.get("section_path") or "").strip()
    content = str(doc.get("content") or "").strip()
    graph_evidence = str(metadata.get("graph_evidence") or "").strip()
    evidence_texts = _rerank_evidence_texts(metadata)

    lines: list[str] = []
    if title:
        lines.append(f"[标题] {title}")
    if section_path:
        lines.append(f"[位置] {section_path}")
    lines.extend(f"[命中片段] {text}" for text in evidence_texts)
    context = _centered_rerank_context(
        content,
        evidence_texts=evidence_texts,
        limit=(
            FINAL_RERANK_CONTEXT_MAX_CHARS
            if evidence_texts
            else FINAL_RERANK_TEXT_MAX_CHARS
        ),
    )
    if context and context.casefold() not in {text.casefold() for text in evidence_texts}:
        lines.append(f"[父级上下文] {context}")
    if graph_evidence:
        lines.append(f"[图谱关系] {graph_evidence}")
    return "\n".join(lines).strip() or content


def _clip_rerank_text(text: str, *, limit: int = FINAL_RERANK_TEXT_MAX_CHARS) -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit]


def _final_rerank_candidate_limit(total_count: int, top_k: int) -> int:
    if total_count <= 0:
        return 0
    safe_top_k = max(1, int(top_k or 1))
    return min(
        total_count,
        max(safe_top_k, safe_top_k * FINAL_RERANK_CANDIDATE_MULTIPLIER),
    )


def _is_graph_rerank_candidate(doc: dict[str, Any]) -> bool:
    source = str((doc.get("metadata") or {}).get("source") or "").strip()
    return source == TEXT_GRAPH_RERANK_SOURCE or source.startswith(GRAPH_RERANK_SOURCE_PREFIX)


def _passes_final_rerank_threshold(doc: dict[str, Any], threshold: float | None) -> bool:
    if threshold is None:
        return True
    raw_score = (doc.get("metadata") or {}).get("rerank_score")
    if raw_score is None:
        return True
    try:
        return float(raw_score) >= threshold
    except (TypeError, ValueError):
        return False


def _select_final_rerank_candidates(
    docs: list[dict[str, Any]],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    candidate_limit = _final_rerank_candidate_limit(len(docs), top_k)
    if candidate_limit <= 0:
        return []
    if len(docs) <= candidate_limit:
        return list(docs)

    text_docs = [doc for doc in docs if not _is_graph_rerank_candidate(doc)]
    graph_docs = [doc for doc in docs if _is_graph_rerank_candidate(doc)]
    if not text_docs or not graph_docs:
        return docs[:candidate_limit]

    safe_top_k = max(1, int(top_k or 1))
    graph_keep = min(len(graph_docs), max(1, min(safe_top_k, candidate_limit // 2)))
    text_keep = candidate_limit - graph_keep
    selected = [*text_docs[:text_keep], *graph_docs[:graph_keep]]

    if len(selected) < candidate_limit:
        selected_ids = {id(doc) for doc in selected}
        for doc in docs:
            if id(doc) in selected_ids:
                continue
            selected.append(doc)
            selected_ids.add(id(doc))
            if len(selected) >= candidate_limit:
                break

    return selected[:candidate_limit]


async def rerank_retrieved_docs(
    query: str,
    docs: list[dict[str, Any]],
    top_k: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_limit = _final_rerank_candidate_limit(len(docs), top_k)
    candidate_docs = _select_final_rerank_candidates(docs, top_k=top_k)
    graph_input_count = len([doc for doc in candidate_docs if _is_graph_rerank_candidate(doc)])
    rerank_threshold = config_registry.get_rag_config().retrieval.rerank_threshold
    trace = {
        "enabled": True,
        "candidate_count": len(docs),
        "candidate_limit": candidate_limit,
        "input_count": len(candidate_docs),
        "hit_text_input_count": len(
            [
                doc
                for doc in candidate_docs
                if _rerank_evidence_texts(dict(doc.get("metadata") or {}))
            ]
        ),
        "text_input_count": len(candidate_docs) - graph_input_count,
        "graph_input_count": graph_input_count,
        "output_count": 0,
        "latency_ms": 0,
        "truncated": len(candidate_docs) < len(docs),
        "max_text_chars": FINAL_RERANK_TEXT_MAX_CHARS,
        "rerank_threshold": rerank_threshold,
        "threshold_filtered_count": 0,
    }
    if not candidate_docs:
        return [], trace
    rerank_inputs = [
        {
            "chunk_text": str(doc.get("content") or ""),
            "search_text": _clip_rerank_text(_build_rerank_text(doc)),
            "document_chunk_id": (doc.get("metadata") or {}).get("document_chunk_id"),
            "_index": index,
        }
        for index, doc in enumerate(candidate_docs)
    ]
    started_at = perf_counter()
    reranked_rows = await rerank(query, rerank_inputs, top_k=top_k)
    trace["latency_ms"] = int((perf_counter() - started_at) * 1000)
    ordered_docs: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()
    for row in reranked_rows:
        index = row.get("_index")
        if not isinstance(index, int) or index in seen_indexes or index >= len(candidate_docs):
            continue
        metadata = {**dict(candidate_docs[index].get("metadata") or {})}
        if row.get("rerank_score") is not None:
            metadata["rerank_score"] = row.get("rerank_score")
        ordered_docs.append({"content": candidate_docs[index].get("content") or "", "metadata": metadata})
        seen_indexes.add(index)
    if len(ordered_docs) < min(top_k, len(candidate_docs)):
        for index, doc in enumerate(candidate_docs):
            if index in seen_indexes:
                continue
            ordered_docs.append(doc)
            if len(ordered_docs) >= min(top_k, len(candidate_docs)):
                break
    ordered_docs = ordered_docs[:top_k]
    filtered_docs = [
        doc for doc in ordered_docs if _passes_final_rerank_threshold(doc, rerank_threshold)
    ]
    threshold_filtered_count = len(ordered_docs) - len(filtered_docs)
    if threshold_filtered_count:
        logger.info(
            "[KB Retrieval] final rerank filtering removed {} of {} candidates | rerank_threshold={}",
            threshold_filtered_count,
            len(ordered_docs),
            rerank_threshold,
        )
    trace["threshold_filtered_count"] = threshold_filtered_count
    trace["output_count"] = len(filtered_docs)
    return filtered_docs, trace


def _resolve_graph_mode_from_plan(graph_plan: dict[str, Any]) -> str | None:
    explicit_mode = str(graph_plan.get("graph_mode") or "").strip()
    if explicit_mode:
        return explicit_mode

    intent = str(graph_plan.get("intent") or "").strip().lower()
    if intent == "relation_lookup":
        return "relation_evidence"
    if intent in {"entity_summary", "neighborhood_lookup"}:
        return "disabled"
    return None


def _classify_evidence(doc: dict[str, Any]) -> str:
    metadata = dict(doc.get("metadata") or {})
    source = str(metadata.get("source") or "").strip()
    document_chunk_id = metadata.get("document_chunk_id")

    if source == "graph":
        return "primary" if document_chunk_id is not None else "metadata"

    if source in {"text_graph", "text", ""}:
        return "primary"

    return "metadata"


def _evidence_ref_id(doc: dict[str, Any]) -> str:
    metadata = dict(doc.get("metadata") or {})
    chunk_id = metadata.get("document_chunk_id")
    if chunk_id is not None:
        return f"chunk:{chunk_id}"
    source = str(metadata.get("source") or "evidence").strip().lower()
    graph_key = str(metadata.get("graph_key") or "").strip()
    relation_type = str(metadata.get("graph_relation_type") or "").strip()
    if graph_key:
        return f"{source}:{graph_key}:{relation_type}".rstrip(":")
    identity = "|".join(
        [
            source,
            str(metadata.get("document_id") or ""),
            str(metadata.get("document_title") or ""),
            str(doc.get("content") or ""),
        ]
    )
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    return f"{source}:{digest}"


def _evidence_kind(doc: dict[str, Any]) -> str:
    source = str((doc.get("metadata") or {}).get("source") or "text").strip().lower()
    return {
        "text": "document_chunk",
        "text_graph": "document_chunk_with_graph",
        "graph": "graph_relation",
        "graph_relation": "graph_relation",
        "graph_relation_evidence": "graph_relation",
        "graph_path": "graph_path",
        "graph_entity": "graph_entity",
    }.get(source, "document_chunk")


def _build_evidence_item(doc: dict[str, Any], *, role: str) -> dict[str, Any] | None:
    content = str(doc.get("content") or "").strip()
    if not content:
        return None
    metadata = dict(doc.get("metadata") or {})
    graph_evidence = str(metadata.get("graph_evidence") or "").strip()
    if graph_evidence and graph_evidence not in content:
        content = f"{content}\n[图谱关系] {graph_evidence}"
    return {
        "ref_id": _evidence_ref_id(doc),
        "role": role,
        "kind": _evidence_kind(doc),
        "content": content,
        "source": {
            "document_id": metadata.get("document_id"),
            "document_chunk_id": metadata.get("document_chunk_id"),
            "document_title": metadata.get("document_title"),
            "section_path": metadata.get("section_path"),
            "source_type": metadata.get("source") or "text",
            "subtask_id": metadata.get("subtask_id"),
        },
    }


def _dedupe_evidence_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    indexes: dict[str, int] = {}
    for item in items:
        ref_id = str(item.get("ref_id") or "").strip()
        if not ref_id:
            continue
        normalized_content = " ".join(str(item.get("content") or "").split()).casefold()
        content_key = (
            f"content:{hashlib.sha1(normalized_content.encode('utf-8')).hexdigest()[:16]}"
            if normalized_content
            else ""
        )
        existing_index = indexes.get(ref_id)
        if existing_index is None and content_key:
            existing_index = indexes.get(content_key)
        if existing_index is None:
            indexes[ref_id] = len(deduped)
            if content_key:
                indexes[content_key] = len(deduped)
            deduped.append(item)
            continue
        existing = deduped[existing_index]
        if existing.get("role") == "supporting" and item.get("role") == "primary":
            deduped[existing_index] = item
    return deduped


def _apply_evidence_budget(
    items: list[dict[str, Any]],
    *,
    max_chars: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if max_chars <= 0:
        return list(items), {
            "max_chars": max_chars,
            "used_chars": sum(len(str(item.get("content") or "")) for item in items),
            "truncated": False,
            "dropped_count": 0,
        }

    kept: list[dict[str, Any]] = []
    used_chars = 0
    truncated = False
    for item in items:
        content = str(item.get("content") or "").strip()
        source = dict(item.get("source") or {})
        header_chars = len(str(source.get("document_title") or "")) + len(
            str(source.get("section_path") or "")
        )
        remaining = max_chars - used_chars - header_chars
        if remaining <= 0:
            truncated = True
            break
        if len(content) > remaining:
            if remaining < 80:
                truncated = True
                break
            item = {**item, "content": content[:remaining].rstrip()}
            content = str(item["content"])
            truncated = True
        kept.append(item)
        used_chars += header_chars + len(content)
        if truncated:
            break

    return kept, {
        "max_chars": max_chars,
        "used_chars": used_chars,
        "truncated": truncated or len(kept) < len(items),
        "dropped_count": max(0, len(items) - len(kept)),
    }


def _empty_text_result(reason: str = "skipped") -> dict[str, Any]:
    return {
        "retrieved_docs": [],
        "context": "",
        "kb_retrieval_status": reason,
        "retrieval_trace": {
            "text_retrieval_latency_ms": 0,
            "total_latency_ms": 0,
            "rerank": {},
            "raw_candidate_count": 0,
            "merged_candidate_count": 0,
        },
    }


def _empty_graph_result(reason: str = "skipped", *, graph_mode: str | None = None) -> dict[str, Any]:
    return {
        "retrieved_docs": [],
        "graph_facts": {"text": [], "entities": [], "relations": [], "paths": [], "evidence": []},
        "trace": {
            "graph_used": False,
            "graph_mode": graph_mode,
            "entity_count": 0,
            "relation_pair_count": 0,
            "relation_query_count": 0,
            "graph_hits": 0,
            "graph_primary_hits": 0,
            "graph_supporting_hits": 0,
            "empty_reason": reason,
            "error": None,
            "latency_ms": 0,
        },
    }


def _extract_seed_terms_from_docs(docs: list[dict[str, Any]], *, limit: int) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for doc in docs:
        metadata = dict(doc.get("metadata") or {})
        candidates = [
            metadata.get("document_title"),
            metadata.get("section_path"),
            metadata.get("graph_key"),
            *list(metadata.get("matched_entities") or []),
        ]
        for candidate in candidates:
            value = " ".join(str(candidate or "").split()).strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            terms.append(value)
            seen.add(key)
            if len(terms) >= limit:
                return terms
    return terms


def _clip_log_text(value: Any, *, limit: int = 220) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _build_graph_evidence_log_items(graph_facts: dict[str, Any], *, limit: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for relation in list(graph_facts.get("relations") or [])[:limit]:
        if not isinstance(relation, dict):
            continue
        source = dict(relation.get("source") or {})
        target = dict(relation.get("target") or {})
        items.append(
            {
                "来源实体": _clip_log_text(source.get("name"), limit=120),
                "关系类型": _clip_log_text(relation.get("relation_type"), limit=120),
                "目标实体": _clip_log_text(target.get("name"), limit=120),
                "证据": _clip_log_text(relation.get("evidence")),
                "文档标题": _clip_log_text(relation.get("document_title"), limit=160),
                "分块ID": relation.get("document_chunk_id"),
            }
        )
    return items


def _write_retrieval_log(payload: dict[str, Any]) -> None:
    logger.bind(kb_retrieval_log=True).info(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    )


async def knowledge_qa_retrieve_node(
    state: KnowledgeQaState,
    *,
    node_id: str = "retrieve_knowledge",
    coverage_llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    if str(state.get("retrieval_strategy") or "").strip().lower() == "skip":
        return {
            "retrieval_result": {
                "status": "no_hits",
                "reason_code": "skipped",
                "evidence_items": [],
                "budget": {
                    "max_chars": 0,
                    "used_chars": 0,
                    "truncated": False,
                    "dropped_count": 0,
                },
                "metrics": {
                    "primary_count": 0,
                    "supporting_count": 0,
                    "text_hit_count": 0,
                    "graph_hit_count": 0,
                    "rerank_input_count": 0,
                    "rerank_output_count": 0,
                },
                "warnings": [],
            },
        }

    emit_activity(
        stream_writer,
        workflow_id="knowledge_qa",
        node_id=node_id,
        stage="retrieve",
        message="正在查找知识库内容",
        display_stage="execute",
        display_title="🔍 查阅相关资料",
        activity_text="查找知识库资料",
    )
    query = str(state.get("query") or "").strip()
    ambiguity = dict(state.get("ambiguity") or {})
    if ambiguity.get("needs_clarification"):
        question = str(ambiguity.get("clarification_question") or "").strip()
        return {
            "retrieval_result": {
                "status": "needs_clarification",
                "reason_code": "ambiguous_query",
                "clarification_question": question,
                "evidence_items": [],
                "subtask_results": [],
                "coverage_complete": False,
                "budget": {
                    "max_chars": 0,
                    "used_chars": 0,
                    "truncated": False,
                    "dropped_count": 0,
                },
                "metrics": {
                    "primary_count": 0,
                    "supporting_count": 0,
                    "text_hit_count": 0,
                    "graph_hit_count": 0,
                    "rerank_input_count": 0,
                    "rerank_output_count": 0,
                },
                "warnings": [],
            }
        }

    subtasks = [
        dict(item)
        for item in list(state.get("retrieval_subtasks") or [])
        if isinstance(item, dict)
    ]
    if not subtasks:
        raise ValueError("知识库检索缺少 retrieval_subtasks")

    execution_plan = dict(state.get("retrieval_execution_plan") or {})
    channels = dict(execution_plan.get("channels") or {})
    vector_plan = dict(channels.get("vector") or {})
    lexical_plan = dict(channels.get("lexical") or {})
    rerank_plan = dict(execution_plan.get("rerank") or {})
    context_plan = dict(execution_plan.get("context") or {})
    final_top_k = int(context_plan.get("final_top_k") or 8)
    llm_reference_top_k = int(context_plan.get("llm_reference_top_k") or final_top_k)
    final_primary_limit = max(1, min(final_top_k, llm_reference_top_k))
    context_budget = int(context_plan.get("budget_chars") or 9000)
    recall_k = max(8, int(vector_plan.get("recall_k") or final_top_k) // len(subtasks))
    lexical_k = max(6, int(lexical_plan.get("lexical_k") or final_top_k) // len(subtasks))
    candidate_limit = max(8, min(recall_k + lexical_k, final_primary_limit * 3))
    per_subtask_top_k = max(2, (final_primary_limit + len(subtasks) - 1) // len(subtasks))
    rerank_enabled = bool(settings.RERANK_ENABLED) and bool(rerank_plan.get("enabled"))
    standalone_query = str(state.get("standalone_query") or query).strip()

    async def _retrieve_subtask(subtask: dict[str, Any]) -> dict[str, Any]:
        subtask_id = str(subtask.get("id") or "").strip()
        goal = str(subtask.get("goal") or "").strip()
        planned_semantic_queries = list(subtask.get("semantic_queries") or [])
        parameter_abstract_queries = list(
            subtask.get("parameter_abstract_queries") or []
        )
        semantic_queries = _dedupe_queries(
            [
                query,
                standalone_query,
                goal,
                *planned_semantic_queries[:1],
                *parameter_abstract_queries[:1],
                *planned_semantic_queries[1:],
                *parameter_abstract_queries[1:],
            ]
        )[:5]
        lexical_terms = _dedupe_terms(
            [
                *list(subtask.get("lexical_terms") or []),
                *list(state.get("business_objects") or []),
            ]
        )[:8]
        try:
            text_result = await run_kb_channel_text_retrieval(
                query=goal,
                semantic_queries=semantic_queries,
                lexical_terms=lexical_terms,
                team_id=state.get("team_id"),
                knowledge_base_id=state.get("knowledge_base_id"),
                category_id=state.get("category_id"),
                log_prefix=f"[User KB Retrieval][{subtask_id}]",
                user_id=state.get("user_id"),
                result_limit=candidate_limit,
                llm_reference_top_k=candidate_limit,
                context_budget=0,
                document_statuses=state.get("allowed_document_statuses"),
                recall_k=recall_k,
                lexical_k=lexical_k,
                rerank_enabled=rerank_enabled,
            )
        except (httpx.HTTPError, OSError, TimeoutError) as exc:
            logger.warning(
                "[KB Retrieval] provider failure | subtask_id={} error_type={}",
                subtask_id,
                type(exc).__name__,
            )
            return {
                "id": subtask_id,
                "goal": goal,
                "evidence_requirement": subtask.get("evidence_requirement"),
                "semantic_queries": semantic_queries,
                "parameter_abstract_queries": parameter_abstract_queries,
                "lexical_terms": lexical_terms,
                "retrieved_docs": [],
                "supporting_docs": [],
                "raw_hit_count": 0,
                "covered": False,
                "top_score": None,
                "rerank": {},
                "retrieval_trace": {},
                "empty_reason": "provider_error",
                "provider_error": {
                    "code": "RETRIEVAL_PROVIDER_ERROR",
                    "type": type(exc).__name__,
                },
            }
        retrieved_docs = list(text_result.get("retrieved_docs") or [])
        primary_docs = [doc for doc in retrieved_docs if _classify_evidence(doc) == "primary"]
        supporting_docs = [doc for doc in retrieved_docs if _classify_evidence(doc) != "primary"]
        trace = dict(text_result.get("retrieval_trace") or {})
        child_rerank_trace = dict(trace.get("rerank") or {})
        ranked_docs = primary_docs[:per_subtask_top_k]
        rerank_trace = {
            **child_rerank_trace,
            "stage": "child_chunk",
            "enabled": bool(child_rerank_trace.get("rerank_enabled")),
            "input_count": int(child_rerank_trace.get("candidate_count") or 0),
            "output_count": int(child_rerank_trace.get("final_count") or 0),
        }
        empty_reason = None
        if not ranked_docs:
            if (
                primary_docs
                and int(rerank_trace.get("threshold_filtered_count") or 0) > 0
            ):
                empty_reason = "below_rerank_threshold"
            else:
                empty_reason = text_result.get("kb_retrieval_status") or "no_hits"
        annotated_docs: list[dict[str, Any]] = []
        for doc in ranked_docs:
            annotated = dict(doc)
            annotated["metadata"] = {
                **dict(doc.get("metadata") or {}),
                "subtask_id": subtask_id,
                "subtask_goal": goal,
                "evidence_requirement": subtask.get("evidence_requirement"),
            }
            annotated_docs.append(annotated)
        return {
            "id": subtask_id,
            "goal": goal,
            "evidence_requirement": subtask.get("evidence_requirement"),
            "semantic_queries": semantic_queries,
            "parameter_abstract_queries": parameter_abstract_queries,
            "lexical_terms": lexical_terms,
            "retrieved_docs": annotated_docs,
            "supporting_docs": supporting_docs,
            "raw_hit_count": len(retrieved_docs),
            "covered": bool(annotated_docs),
            "top_score": (
                (annotated_docs[0].get("metadata") or {}).get("rerank_score")
                if annotated_docs
                else None
            ),
            "rerank": rerank_trace,
            "retrieval_trace": trace,
            "empty_reason": empty_reason,
        }

    emit_activity(
        stream_writer,
        workflow_id="knowledge_qa",
        node_id=node_id,
        stage="retrieve",
        message="正在按子任务并行检索知识库",
        display_stage="execute",
        display_title="🔍 查阅相关资料",
        activity_text=f"并行查找 {len(subtasks)} 个检索子任务",
        subtask_count=len(subtasks),
    )
    subtask_results = await asyncio.gather(
        *[_retrieve_subtask(subtask) for subtask in subtasks]
    )
    coverage_audit = await assess_subtask_coverage(
        subtask_results,
        llm_factory=coverage_llm_factory,
    )
    audit_by_id = {
        str(item.get("id") or "").strip(): dict(item)
        for item in list(coverage_audit.get("subtasks") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    provider_errors = [
        dict(result.get("provider_error") or {})
        for result in subtask_results
        if result.get("provider_error")
    ]

    selected_docs: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for rank_index in range(per_subtask_top_k):
        for result in subtask_results:
            audit = audit_by_id.get(str(result.get("id") or ""), {})
            audit_status = str(audit.get("status") or "missed")
            if audit_status not in {"covered", "partial", "weak"}:
                continue
            docs = list(result.get("retrieved_docs") or [])
            if rank_index >= len(docs):
                continue
            supported_indices = {
                int(index)
                for index in list(audit.get("supported_evidence_indices") or [])
                if str(index).strip().isdigit()
            }
            if audit_status == "covered" and not supported_indices:
                supported_indices = set(range(1, len(docs) + 1))
            if rank_index + 1 not in supported_indices:
                continue
            doc = docs[rank_index]
            ref_id = _evidence_ref_id(doc)
            if ref_id in seen_refs:
                continue
            seen_refs.add(ref_id)
            selected_docs.append(doc)
            if len(selected_docs) >= final_primary_limit:
                break
        if len(selected_docs) >= final_primary_limit:
            break

    supporting_docs = [
        doc
        for result in subtask_results
        if audit_by_id.get(str(result.get("id") or ""), {}).get("status") == "covered"
        for doc in list(result.get("supporting_docs") or [])
    ]
    current_evidence_candidates = [
        *[
            item
            for doc in selected_docs
            if (item := _build_evidence_item(doc, role="primary")) is not None
        ],
        *[
            item
            for doc in supporting_docs
            if (item := _build_evidence_item(doc, role="supporting")) is not None
        ],
    ]
    accumulated_evidence_items = [
        dict(item)
        for item in list(state.get("accumulated_evidence_items") or [])
        if isinstance(item, dict)
    ]
    evidence_items, budget = _apply_evidence_budget(
        _dedupe_evidence_items(
            [
                *accumulated_evidence_items,
                *current_evidence_candidates,
            ]
        ),
        max_chars=context_budget,
    )
    primary_ref_ids = {
        str(item.get("ref_id") or "")
        for item in evidence_items
        if item.get("role") == "primary"
    }
    current_subtask_results: list[dict[str, Any]] = []
    for result in subtask_results:
        subtask_id = str(result.get("id") or "")
        audit = audit_by_id.get(subtask_id, {})
        evidence_refs = [
            _evidence_ref_id(doc)
            for doc in list(result.get("retrieved_docs") or [])
            if _evidence_ref_id(doc) in primary_ref_ids
        ]
        coverage_status = str(audit.get("status") or "missed")
        if coverage_status == "weak":
            coverage_status = "partial"
        is_answerable = bool(evidence_refs) and coverage_status in {
            "covered",
            "partial",
        }
        current_subtask_results.append(
            {
                "id": subtask_id,
                "goal": result.get("goal"),
                "evidence_requirement": result.get("evidence_requirement"),
                "covered": coverage_status == "covered" and bool(evidence_refs),
                "answerable": is_answerable,
                "coverage_status": coverage_status,
                "failure_reason": audit.get("failure_reason") or result.get("empty_reason"),
                "coverage_reason": audit.get("reason"),
                "supported_claims": list(audit.get("supported_claims") or []),
                "discovered_terms": list(audit.get("discovered_terms") or []),
                "evidence_refs": evidence_refs,
                "top_score": result.get("top_score"),
                "raw_hit_count": result.get("raw_hit_count"),
                "empty_reason": result.get("empty_reason"),
                "provider_error": dict(result.get("provider_error") or {}),
            }
        )

    coverage_by_id = {
        str(item.get("id") or ""): dict(item)
        for item in list(state.get("subtask_coverage") or [])
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    for item in current_subtask_results:
        coverage_by_id[str(item.get("id") or "")] = item
    compact_subtask_results = list(coverage_by_id.values())
    uncovered = [item for item in compact_subtask_results if not item["covered"]]
    retryable_subtasks = [
        item
        for item in compact_subtask_results
        if not item.get("answerable") and not item.get("provider_error")
    ]
    final_hits = len(primary_ref_ids)
    supporting_hits = len(evidence_items) - final_hits
    coverage_complete = not uncovered
    warnings = (
        []
        if coverage_complete
        else [
            {
                "code": "PARTIAL_SUBTASK_COVERAGE",
                "message": "部分检索子任务证据覆盖不完整，仅用于检索诊断。",
                "subtask_ids": [item["id"] for item in uncovered],
            }
        ]
    )
    current_text_hits = sum(int(item.get("raw_hit_count") or 0) for item in subtask_results)
    current_rerank_inputs = sum(
        int((item.get("rerank") or {}).get("input_count") or 0)
        for item in subtask_results
    )
    current_rerank_outputs = sum(
        int((item.get("rerank") or {}).get("output_count") or 0)
        for item in subtask_results
    )
    previous_attempts = [
        dict(item)
        for item in list(state.get("retrieval_attempts") or [])
        if isinstance(item, dict)
    ]
    attempt_number = max(1, int(state.get("query_plan_attempt") or 1))
    used_queries = _dedupe_queries(
        [
            *[
                str(query)
                for attempt in previous_attempts
                for query in list(attempt.get("used_queries") or [])
            ],
            *[
                str(query)
                for result in subtask_results
                for query in [
                    *list(result.get("semantic_queries") or []),
                    *list(result.get("lexical_terms") or []),
                ]
            ],
        ]
    )
    attempt_record = {
        "attempt": attempt_number,
        "used_queries": used_queries,
        "subtask_results": current_subtask_results,
        "coverage_audit": dict(coverage_audit),
        "metrics": {
            "text_hit_count": current_text_hits,
            "rerank_input_count": current_rerank_inputs,
            "rerank_output_count": current_rerank_outputs,
        },
    }
    retrieval_attempts = [*previous_attempts, attempt_record]
    total_text_hits = sum(
        int((item.get("metrics") or {}).get("text_hit_count") or 0)
        for item in retrieval_attempts
    )
    total_rerank_inputs = sum(
        int((item.get("metrics") or {}).get("rerank_input_count") or 0)
        for item in retrieval_attempts
    )
    total_rerank_outputs = sum(
        int((item.get("metrics") or {}).get("rerank_output_count") or 0)
        for item in retrieval_attempts
    )
    should_replan = (
        bool(retryable_subtasks)
        and final_hits == 0
        and attempt_number < 2
        and not provider_errors
    )
    subtask_by_id = {
        str(item.get("id") or ""): dict(item)
        for item in subtasks
        if str(item.get("id") or "")
    }
    failed_subtasks: list[dict[str, Any]] = []
    for item in current_subtask_results:
        if item.get("answerable") or item.get("provider_error"):
            continue
        subtask = subtask_by_id.get(str(item.get("id") or ""), {})
        result = next(
            (
                candidate
                for candidate in subtask_results
                if candidate.get("id") == item.get("id")
            ),
            {},
        )
        candidate_clues = [
            {
                "document_title": (doc.get("metadata") or {}).get("document_title"),
                "section_path": (doc.get("metadata") or {}).get("section_path"),
                "content": " ".join(str(doc.get("content") or "").split())[:500],
            }
            for doc in list(result.get("retrieved_docs") or [])[:4]
        ]
        failed_subtasks.append(
            {
                **subtask,
                "failure_reason": item.get("failure_reason"),
                "coverage_reason": item.get("coverage_reason"),
                "discovered_terms": list(item.get("discovered_terms") or []),
                "candidate_clues": candidate_clues,
            }
        )
    retrieval_feedback = {
        "failed_subtasks": failed_subtasks,
        "used_queries": used_queries,
        "attempt": attempt_number,
    }
    _write_retrieval_log(
        {
            "日志类型": "知识库检索",
            "阶段": "检索完成",
            "问题": {
                "原始问题": query,
                "独立问题": standalone_query,
                "业务对象": list(state.get("business_objects") or []),
                "用户动作": state.get("action"),
                "参数": dict(state.get("query_parameters") or {}),
            },
            "子任务检索": [
                {
                    "子任务ID": item.get("id"),
                    "目标": item.get("goal"),
                    "证据要求": item.get("evidence_requirement"),
                    "语义查询": item.get("semantic_queries"),
                    "参数抽象查询": item.get("parameter_abstract_queries"),
                    "精确关键词": item.get("lexical_terms"),
                    "原始命中数": item.get("raw_hit_count"),
                    "最终覆盖": next(
                        (
                            compact["covered"]
                            for compact in compact_subtask_results
                            if compact["id"] == item.get("id")
                        ),
                        False,
                    ),
                    "精排": item.get("rerank"),
                    "证据审计": audit_by_id.get(str(item.get("id") or "")),
                    "空结果原因": item.get("empty_reason"),
                }
                for item in subtask_results
            ],
            "证据覆盖": {
                "是否完整": coverage_complete,
                "已覆盖子任务数": len(compact_subtask_results) - len(uncovered),
                "总子任务数": len(compact_subtask_results),
                "最终主证据数": final_hits,
                "最终辅助证据数": supporting_hits,
                "是否触发二次规划": should_replan,
            },
        }
    )
    empty_reasons = {
        str(item.get("empty_reason") or "").strip()
        for item in subtask_results
        if str(item.get("empty_reason") or "").strip()
    }
    if provider_errors and not final_hits:
        reason_code = "provider_error"
    elif final_hits:
        reason_code = None
    elif "empty_knowledge_base" in empty_reasons:
        reason_code = "empty_knowledge_base"
    elif "below_rerank_threshold" in empty_reasons:
        reason_code = "below_rerank_threshold"
    else:
        reason_code = "no_hits"
    status = (
        "replan_required"
        if should_replan
        else "provider_error"
        if provider_errors and not final_hits
        else "found"
        if final_hits
        else "no_hits"
    )
    if provider_errors:
        warnings.append(
            {
                "code": "RETRIEVAL_PROVIDER_ERROR",
                "message": "部分知识库检索服务暂时不可用。",
            }
        )
    return {
        "should_replan": should_replan,
        "retrieval_feedback": retrieval_feedback,
        "retrieval_attempts": retrieval_attempts,
        "accumulated_evidence_items": evidence_items,
        "subtask_coverage": compact_subtask_results,
        "retrieval_result": {
            "status": status,
            "reason_code": reason_code,
            "evidence_items": evidence_items,
            "subtask_results": compact_subtask_results,
            "coverage_complete": coverage_complete,
            "coverage_audit": dict(coverage_audit),
            "attempt_count": len(retrieval_attempts),
            "budget": budget,
            "metrics": {
                "primary_count": final_hits,
                "supporting_count": supporting_hits,
                "text_hit_count": total_text_hits,
                "graph_hit_count": 0,
                "rerank_input_count": total_rerank_inputs,
                "rerank_output_count": total_rerank_outputs,
            },
            "warnings": warnings,
        }
    }
