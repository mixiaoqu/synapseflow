"""Text and graph retrieval node for knowledge-base chat."""

from __future__ import annotations

import asyncio
import json
from time import perf_counter
from typing import Any

from loguru import logger

from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.states import KnowledgeQaState
from app.core.config.registry import config_registry
from app.core.config.settings import settings
from app.services.chat_memory import format_chat_history
from app.services.graph_entity_candidate_service import resolve_graph_candidate_entities
from app.services.graph_document_scope import resolve_graph_category_document_ids
from app.services.kb_graph_retrieval import GraphRetriever
from app.services.kb_text_retrieval import run_kb_channel_text_retrieval
from app.services.reranker import rerank

FINAL_RERANK_CANDIDATE_MULTIPLIER = 2
FINAL_RERANK_TEXT_MAX_CHARS = 1200
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
            "document_title": f"{source_display} -> {target_display}",
            "section_path": None,
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


def _build_context(docs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for index, doc in enumerate(docs, start=1):
        metadata = dict(doc.get("metadata") or {})
        title = metadata.get("document_title") or f"Evidence {index}"
        evidence = metadata.get("graph_evidence")
        content = str(doc.get("content") or "").strip()
        if evidence and evidence not in content:
            content = f"{content}\nGraph evidence: {evidence}".strip()
        if content:
            parts.append(f"[{index}] {title}\n{content}")
    return "\n\n".join(parts)


def _build_supporting_context(docs: list[dict[str, Any]]) -> str:
    section_order = ("实体", "关系", "路径", "关系证据")
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in section_order}
    extras: list[dict[str, Any]] = []
    for doc in docs:
        section = str((doc.get("metadata") or {}).get("supporting_section") or "").strip()
        if section in grouped:
            grouped[section].append(doc)
        else:
            extras.append(doc)

    parts: list[str] = []
    for section in section_order:
        section_docs = grouped[section]
        if not section_docs:
            continue
        blocks = [
            _format_doc_for_layer(doc, index=index)
            for index, doc in enumerate(section_docs, start=1)
            if _format_doc_for_layer(doc, index=index)
        ]
        if blocks:
            parts.append(f"[{section}]\n" + "\n\n".join(blocks))

    if extras:
        extra_blocks = [
            _format_doc_for_layer(doc, index=index)
            for index, doc in enumerate(extras, start=1)
            if _format_doc_for_layer(doc, index=index)
        ]
        if extra_blocks:
            parts.append("[补充信息]\n" + "\n\n".join(extra_blocks))
    return "\n\n".join(parts)


def _build_rerank_text(doc: dict[str, Any]) -> str:
    metadata = dict(doc.get("metadata") or {})
    title = str(metadata.get("document_title") or "").strip()
    section_path = str(metadata.get("section_path") or "").strip()
    content = str(doc.get("content") or "").strip()
    graph_evidence = str(metadata.get("graph_evidence") or "").strip()

    lines: list[str] = []
    if title:
        lines.append(f"[标题] {title}")
    if section_path:
        lines.append(f"[位置] {section_path}")
    if content:
        lines.append(f"[原文] {content}")
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


def _classify_evidence(doc: dict[str, Any], *, question_type: str) -> str:
    metadata = dict(doc.get("metadata") or {})
    source = str(metadata.get("source") or "").strip()
    document_chunk_id = metadata.get("document_chunk_id")

    if source == "graph":
        return "primary" if document_chunk_id is not None else "metadata"

    if source in {"text_graph", "text", ""}:
        return "primary"

    return "metadata"


def _format_doc_for_layer(doc: dict[str, Any], *, index: int) -> str:
    metadata = dict(doc.get("metadata") or {})
    title = str(metadata.get("document_title") or f"Evidence {index}").strip()
    section_path = str(metadata.get("section_path") or "").strip()
    content = str(doc.get("content") or "").strip()
    graph_evidence = str(metadata.get("graph_evidence") or "").strip()

    lines = [f"[{index}] {title}"]
    if section_path:
        lines.append(f"位置：{section_path}")
    if content:
        lines.append(content)
    if graph_evidence and graph_evidence not in content:
        lines.append(f"补充关系：{graph_evidence}")
    return "\n".join(lines).strip()


def _build_layer_context(docs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for index, doc in enumerate(docs, start=1):
        block = _format_doc_for_layer(doc, index=index)
        if block:
            parts.append(block)
    return "\n\n".join(parts)


def _compose_full_context(
    *,
    primary_context: str,
    supporting_context: str,
) -> str:
    sections: list[str] = []
    if primary_context.strip():
        sections.append(f"[Primary evidence]\n{primary_context.strip()}")
    if supporting_context.strip():
        sections.append(f"[Supporting evidence]\n{supporting_context.strip()}")
    return "\n\n".join(sections).strip()


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


async def kb_chat_retrieve_node(
    state: KnowledgeQaState,
    *,
    node_id: str = "retrieve_knowledge",
) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    if str(state.get("retrieval_strategy") or "").strip().lower() == "skip":
        return {
            "retrieved_docs": [],
            "graph_facts": {"text": [], "entities": [], "relations": [], "paths": [], "evidence": []},
            "primary_evidence_docs": [],
            "supporting_evidence_docs": [],
            "primary_context": "",
            "supporting_context": "",
            "context": "",
            "retrieval_trace": {
                "retrieval_strategy": "skip",
                "text": {"skipped": True, "text_hits": 0},
                "graph": {"graph_used": False, "graph_hits": 0, "empty_reason": "skipped"},
                "final_hits": 0,
                "empty_reason": "skipped",
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
    semantic_queries = _dedupe_queries(
        [
            str(item).strip()
            for item in list(state.get("semantic_queries") or [])
            if str(item or "").strip()
        ]
    ) or [query]
    lexical_terms = _dedupe_terms(
        [
            *[
                str(item).strip()
                for item in list(state.get("lexical_terms") or [])
                if str(item or "").strip()
            ],
            *[
                str(item).strip()
                for item in list(state.get("target_attributes") or [])
                if str(item or "").strip()
            ],
        ]
    )
    candidate_entities = [
        str(item).strip()
        for item in list(state.get("candidate_entities") or [])
        if str(item or "").strip()
    ]

    execution_plan = dict(state.get("retrieval_execution_plan") or {})
    channels = dict(execution_plan.get("channels") or {})
    vector_plan = dict(channels.get("vector") or {})
    lexical_plan = dict(channels.get("lexical") or {})
    graph_plan = dict(channels.get("graph") or {})
    rerank_plan = dict(execution_plan.get("rerank") or {})
    context_plan = dict(execution_plan.get("context") or {})
    retrieval_strategy = str(
        execution_plan.get("mode") or state.get("retrieval_strategy") or "parallel_fusion"
    ).strip().lower()
    text_enabled = bool(vector_plan.get("enabled", True)) or bool(lexical_plan.get("enabled", True))
    final_top_k = int(context_plan.get("final_top_k") or 8)
    llm_reference_top_k = int(context_plan.get("llm_reference_top_k") or final_top_k)
    recall_k = int(vector_plan.get("recall_k") or final_top_k)
    lexical_k = int(lexical_plan.get("lexical_k") or final_top_k)
    graph_limit = int(graph_plan.get("limit") or final_top_k)
    graph_enabled = bool(graph_plan.get("enabled", True))
    graph_mode = _resolve_graph_mode_from_plan(graph_plan)
    graph_max_hops = int(graph_plan.get("max_hops") or 1)
    context_budget = int(context_plan.get("budget_chars") or 9000)
    rerank_enabled = bool(settings.RERANK_ENABLED) and bool(rerank_plan.get("enabled"))
    text_candidate_limit = max(final_top_k, min(recall_k + lexical_k, final_top_k * 4))
    question_type = str(state.get("question_type") or "definition_lookup").strip().lower()
    resolved_graph_candidates = {
        "candidate_entities": list(candidate_entities[:graph_limit]),
        "matched_entities": [],
        "trace": {
            "lookup_terms": [],
            "resolved_entities": list(candidate_entities[:graph_limit]),
            "unmatched_terms": [],
            "match_count": 0,
            "fallback_used": True,
            "skipped": not graph_enabled,
        },
    }
    graph_candidate_entities = list(candidate_entities[:graph_limit])
    graph_allowed_document_ids = (
        await resolve_graph_category_document_ids(
            team_id=int(state.get("team_id")) if state.get("team_id") is not None else None,
            knowledge_base_id=int(state.get("knowledge_base_id") or 0),
            category_id=int(state.get("category_id")) if state.get("category_id") is not None else None,
            user_id=int(state.get("user_id")) if state.get("user_id") is not None else None,
            document_statuses=state.get("allowed_document_statuses"),
        )
        if graph_enabled and int(state.get("knowledge_base_id") or 0) > 0 and state.get("category_id") is not None
        else None
    )

    async def _resolve_graph_candidates(seed_entities: list[str]) -> tuple[list[str], dict[str, Any]]:
        fallback = {
            "candidate_entities": list(seed_entities[:graph_limit]),
            "matched_entities": [],
            "trace": {
                "lookup_terms": [],
                "resolved_entities": list(seed_entities[:graph_limit]),
                "unmatched_terms": [],
                "match_count": 0,
                "fallback_used": True,
                "skipped": not graph_enabled,
            },
        }
        if not graph_enabled or int(state.get("knowledge_base_id") or 0) <= 0 or int(state.get("team_id") or 0) <= 0:
            return list(fallback.get("candidate_entities") or []), fallback
        resolved = await resolve_graph_candidate_entities(
            knowledge_base_id=int(state.get("knowledge_base_id") or 0),
            team_id=int(state.get("team_id") or 0),
            query=query,
            candidate_entities=seed_entities,
            lexical_terms=lexical_terms,
            page_context=dict(state.get("page_context") or {}),
            limit=graph_limit,
            allowed_document_ids=graph_allowed_document_ids,
        )
        return list(resolved.get("candidate_entities") or []), resolved

    if graph_enabled and retrieval_strategy != "text_then_graph":
        graph_candidate_entities, resolved_graph_candidates = await _resolve_graph_candidates(candidate_entities)

    common_kwargs = {
        "team_id": state.get("team_id"),
        "knowledge_base_id": state.get("knowledge_base_id"),
        "category_id": state.get("category_id"),
        "log_prefix": "[User KB Retrieval]",
        "user_id": state.get("user_id"),
        "result_limit": text_candidate_limit,
        "llm_reference_top_k": text_candidate_limit,
        "context_budget": context_budget,
        "document_statuses": state.get("allowed_document_statuses"),
        "recall_k": recall_k,
        "lexical_k": lexical_k,
        "rerank_enabled": False,
    }

    async def _run_text_retrieval(
        *,
        search_queries: list[str] | None = None,
        search_terms: list[str] | None = None,
    ) -> dict[str, Any]:
        if not text_enabled:
            return _empty_text_result()
        return await run_kb_channel_text_retrieval(
            query=query,
            semantic_queries=search_queries or semantic_queries,
            lexical_terms=search_terms or lexical_terms,
            **common_kwargs,
        )

    async def _run_graph_retrieval(seed_entities: list[str] | None = None) -> dict[str, Any]:
        if not graph_enabled:
            return _empty_graph_result(graph_mode=graph_mode)
        return await GraphRetriever(enabled=graph_enabled).retrieve(
            knowledge_base_id=int(state.get("knowledge_base_id") or 0),
            team_id=int(state.get("team_id") or 0),
            candidate_entities=seed_entities or graph_candidate_entities,
            relation_pairs=list(state.get("relation_pairs") or []),
            relation_queries=list(state.get("relation_queries") or []),
            question_type=question_type,
            graph_mode=graph_mode,
            max_hops=graph_max_hops,
            limit=graph_limit,
            allowed_document_ids=graph_allowed_document_ids,
        )

    text_result: dict[str, Any]
    graph_result: dict[str, Any]
    if retrieval_strategy == "text_only":
        text_result = await _run_text_retrieval()
        graph_result = _empty_graph_result(graph_mode=graph_mode)
    elif retrieval_strategy == "graph_only":
        graph_result = await _run_graph_retrieval()
        text_result = _empty_text_result()
    elif retrieval_strategy == "text_then_graph":
        text_result = await _run_text_retrieval()
        text_seed_entities = list(candidate_entities)
        if not text_seed_entities:
            text_seed_entities = _dedupe_queries(
                _extract_seed_terms_from_docs(
                    list(text_result.get("retrieved_docs") or []),
                    limit=graph_limit,
                )
            )
        graph_candidate_entities, resolved_graph_candidates = await _resolve_graph_candidates(text_seed_entities)
        graph_result = await _run_graph_retrieval(graph_candidate_entities)
    elif retrieval_strategy == "graph_then_text":
        graph_result = await _run_graph_retrieval()
        graph_seed_terms = _extract_seed_terms_from_docs(
            [
                *_build_graph_docs_from_facts(dict(graph_result.get("graph_facts") or {}))[0],
                *_build_graph_docs_from_facts(dict(graph_result.get("graph_facts") or {}))[1],
            ],
            limit=graph_limit,
        )
        semantic_queries = _dedupe_queries([*semantic_queries, *graph_seed_terms])
        lexical_terms = _dedupe_terms([*lexical_terms, *graph_seed_terms])
        text_result = await _run_text_retrieval(
            search_queries=semantic_queries,
            search_terms=lexical_terms,
        )
    else:
        text_result, graph_result = await asyncio.gather(_run_text_retrieval(), _run_graph_retrieval())

    text_docs = list(text_result.get("retrieved_docs") or [])
    graph_facts = dict(graph_result.get("graph_facts") or {})
    graph_text_docs, graph_supporting_context_docs = _build_graph_docs_from_facts(graph_facts)
    merge_started_at = perf_counter()
    merged_docs = _merge_text_and_graph_docs(
        text_docs,
        graph_text_docs,
        final_top_k=max(final_top_k, len(text_docs) + len(graph_text_docs)),
    )
    duplicates_folded = max(0, len(text_docs) + len(graph_text_docs) - len(merged_docs))
    primary_docs: list[dict[str, Any]] = []
    supporting_text_docs: list[dict[str, Any]] = []
    for doc in merged_docs:
        layer = _classify_evidence(doc, question_type=question_type)
        if layer == "primary":
            primary_docs.append(doc)
        else:
            supporting_text_docs.append(doc)
    if rerank_enabled:
        emit_activity(
            stream_writer,
            workflow_id="knowledge_qa",
            node_id=node_id,
            stage="rerank",
            message="正在对融合证据统一精排",
            display_stage="execute",
            display_title="🔍 查阅相关资料",
            activity_text="筛选更相关的资料",
            candidate_count=len(primary_docs),
            top_k=final_top_k,
        )
        reranked_primary_docs, final_rerank_trace = await rerank_retrieved_docs(
            query,
            primary_docs,
            final_top_k,
        )
    else:
        reranked_primary_docs = primary_docs[:final_top_k]
        final_rerank_trace = {
            "enabled": False,
            "candidate_count": len(primary_docs),
            "input_count": len(primary_docs),
            "output_count": len(reranked_primary_docs),
            "latency_ms": 0,
            "truncated": False,
            "max_text_chars": FINAL_RERANK_TEXT_MAX_CHARS,
            "rerank_threshold": None,
            "threshold_filtered_count": 0,
        }
    supporting_docs = supporting_text_docs + graph_supporting_context_docs
    primary_context = _build_layer_context(reranked_primary_docs)
    supporting_context = _build_supporting_context(supporting_docs)
    context = _compose_full_context(
        primary_context=primary_context,
        supporting_context=supporting_context,
    )
    merge_latency_ms = int((perf_counter() - merge_started_at) * 1000)
    if format_chat_history(state.get("chat_history") or [], max_messages=4):
        text_result["chat_history"] = state.get("chat_history") or []

    final_hits = len(reranked_primary_docs)
    text_trace = dict(text_result.get("retrieval_trace") or {})
    graph_trace = dict(graph_result.get("trace") or {})
    text_rerank_trace = dict(text_trace.get("rerank") or {})
    rerank_trace = {
        "text_stage": text_rerank_trace,
        "final_stage": final_rerank_trace,
        "enabled": rerank_enabled,
        "input_count": final_rerank_trace.get("input_count"),
        "output_count": final_rerank_trace.get("output_count"),
        "latency_ms": final_rerank_trace.get("latency_ms"),
        "rerank_threshold": final_rerank_trace.get("rerank_threshold"),
        "threshold_filtered_count": final_rerank_trace.get("threshold_filtered_count"),
    }
    trace = {
        "retrieval_strategy": retrieval_strategy,
        "text": {
            "skipped": not text_enabled,
            "semantic_query_count": len(semantic_queries),
            "lexical_term_count": len(lexical_terms),
            "text_hits": len(text_docs),
            "empty_reason": (
                None if text_docs else text_result.get("kb_retrieval_status") or "no_hits"
            ),
            "funnel": text_result.get("retrieval_funnel"),
            "latency_ms": text_trace.get("text_retrieval_latency_ms"),
            "raw_candidate_count": text_trace.get("raw_candidate_count"),
            "merged_candidate_count": text_trace.get("merged_candidate_count"),
            "recall_k": recall_k,
            "lexical_k": lexical_k,
        },
        "graph": graph_trace,
        "graph_candidate_resolution": dict(resolved_graph_candidates.get("trace") or {}),
        "rerank": rerank_trace,
        "final_hits": final_hits,
        "empty_reason": None if final_hits else "no_hits",
        "retrieval_complexity": state.get("retrieval_complexity"),
        "execution_plan": execution_plan,
        "total_latency_ms": text_trace.get("total_latency_ms"),
        "merge_latency_ms": merge_latency_ms,
        "primary_count": len(reranked_primary_docs),
        "supporting_count": len(supporting_docs),
        "merged_pool_count": len(primary_docs) + len(supporting_text_docs),
        "duplicates_folded": duplicates_folded,
        "graph_primary_count": len(graph_text_docs),
        "graph_supporting_count": len(supporting_docs),
        "supporting_sections": [
            str((doc.get("metadata") or {}).get("supporting_section") or "").strip()
            for doc in supporting_docs
            if str((doc.get("metadata") or {}).get("supporting_section") or "").strip()
        ],
        "text_evidence_count": len(
            [doc for doc in reranked_primary_docs if (doc.get("metadata") or {}).get("source") != "graph"]
        ),
        "graph_evidence_count": len(
            [
                doc
                for doc in reranked_primary_docs
                if (doc.get("metadata") or {}).get("source")
                in {"graph", "text_graph", "graph_relation", "graph_relation_evidence", "graph_path"}
            ]
        ),
        "final_context_docs": len(reranked_primary_docs),
    }
    graph_evidence_log_items = _build_graph_evidence_log_items(graph_facts)
    _write_retrieval_log(
        {
            "日志类型": "知识库检索",
            "阶段": "检索完成",
            "范围": {
                "团队ID": state.get("team_id"),
                "知识库ID": state.get("knowledge_base_id"),
                "分类ID": state.get("category_id"),
                "用户ID": state.get("user_id"),
            },
            "问题": {
                "原始问题": query,
                "问题类型": question_type,
                "检索复杂度": state.get("retrieval_complexity"),
                "检索策略": retrieval_strategy,
            },
            "检索输入": {
                "语义查询": semantic_queries,
                "关键词": lexical_terms,
                "原始候选实体": candidate_entities,
                "图谱候选实体": graph_candidate_entities,
                "关系对条件": list(state.get("relation_pairs") or []),
                "关系查询条件": list(state.get("relation_queries") or []),
            },
            "图谱实体解析": dict(resolved_graph_candidates.get("trace") or {}),
            "文本检索": {
                "是否跳过": not text_enabled,
                "命中数": len(text_docs),
                "空结果原因": None if text_docs else text_result.get("kb_retrieval_status") or "no_hits",
                "向量召回数": recall_k,
                "关键词召回数": lexical_k,
                "原始候选数": text_trace.get("raw_candidate_count"),
                "合并候选数": text_trace.get("merged_candidate_count"),
                "文本阶段精排": False,
                "耗时毫秒": text_trace.get("text_retrieval_latency_ms"),
            },
            "图谱检索": {
                "是否启用": graph_enabled,
                "图谱模式": graph_trace.get("graph_mode"),
                "图谱命中总数": graph_trace.get("graph_hits"),
                "图谱主证据数": len(graph_text_docs),
                "图谱辅助证据数": len(supporting_docs),
                "空结果原因": graph_trace.get("empty_reason"),
                "错误": graph_trace.get("error"),
                "耗时毫秒": graph_trace.get("latency_ms"),
            },
            "证据融合": {
                "最终主证据数": len(reranked_primary_docs),
                "最终辅助证据数": len(supporting_docs),
                "最终返回数": final_hits,
                "文本证据数": trace["text_evidence_count"],
                "图谱证据数": trace["graph_evidence_count"],
                "折叠重复数": duplicates_folded,
                "辅助证据分组": trace["supporting_sections"],
                "最终精排启用": rerank_trace["enabled"],
                "最终精排输入数": rerank_trace["input_count"],
                "最终精排输出数": rerank_trace["output_count"],
                "最终精排阈值": rerank_trace["rerank_threshold"],
                "最终精排阈值过滤数": rerank_trace["threshold_filtered_count"],
            },
            "图谱关系证据": {
                "样例数量": len(graph_evidence_log_items),
                "总数": len(list(graph_facts.get("relations") or [])),
                "样例": graph_evidence_log_items,
            },
            "性能": {
                "合并耗时毫秒": merge_latency_ms,
                "最终精排耗时毫秒": rerank_trace["latency_ms"],
                "文本总耗时毫秒": text_trace.get("total_latency_ms"),
            },
        }
    )
    return {
        "retrieved_docs": reranked_primary_docs,
        "graph_facts": graph_facts,
        "reranked_primary_evidence_docs": reranked_primary_docs,
        "primary_evidence_docs": reranked_primary_docs,
        "supporting_evidence_docs": supporting_docs,
        "primary_context": primary_context,
        "supporting_context": supporting_context,
        "context": context,
        "retrieval_trace": trace,
    }
