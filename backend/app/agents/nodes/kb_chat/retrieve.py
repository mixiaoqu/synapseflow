"""Text and graph retrieval node for knowledge-base chat."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from loguru import logger

from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatState
from app.core.config.settings import settings
from app.services.chat_memory import format_chat_history
from app.services.kb_graph_retrieval import GraphRetriever
from app.services.kb_text_retrieval import run_kb_channel_text_retrieval
from app.services.reranker import rerank


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
        return ("relation_summary", graph_mode, normalized_name, relation_type)
    return (source, graph_mode, normalized_name, relation_type, str(doc.get("content") or "").strip())


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
            metadata["graph_evidence"] = graph_metadata.get("graph_evidence") or graph_metadata.get("graph_summary")
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
        evidence = metadata.get("graph_evidence") or metadata.get("graph_summary")
        content = str(doc.get("content") or "").strip()
        if evidence and evidence not in content:
            content = f"{content}\nGraph evidence: {evidence}".strip()
        if content:
            parts.append(f"[{index}] {title}\n{content}")
    return "\n\n".join(parts)


def _build_supporting_context(docs: list[dict[str, Any]]) -> str:
    section_order = ("实体摘要", "关键关系", "邻域补充", "关联证据")
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
    graph_evidence = str(metadata.get("graph_evidence") or metadata.get("graph_summary") or "").strip()

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


async def rerank_retrieved_docs(query: str, docs: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    if not docs:
        return []
    rerank_inputs = [
        {
            "chunk_text": str(doc.get("content") or ""),
            "search_text": _build_rerank_text(doc),
            "document_chunk_id": (doc.get("metadata") or {}).get("document_chunk_id"),
            "_index": index,
        }
        for index, doc in enumerate(docs)
    ]
    reranked_rows = await rerank(query, rerank_inputs, top_k=top_k)
    ordered_docs: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()
    for row in reranked_rows:
        index = row.get("_index")
        if not isinstance(index, int) or index in seen_indexes or index >= len(docs):
            continue
        metadata = {**dict(docs[index].get("metadata") or {})}
        if row.get("rerank_score") is not None:
            metadata["rerank_score"] = row.get("rerank_score")
        ordered_docs.append({"content": docs[index].get("content") or "", "metadata": metadata})
        seen_indexes.add(index)
    if len(ordered_docs) < min(top_k, len(docs)):
        for index, doc in enumerate(docs):
            if index in seen_indexes:
                continue
            ordered_docs.append(doc)
            if len(ordered_docs) >= min(top_k, len(docs)):
                break
    return ordered_docs[:top_k]


def _resolve_graph_mode_from_plan(graph_plan: dict[str, Any]) -> str | None:
    explicit_mode = str(graph_plan.get("graph_mode") or "").strip()
    if explicit_mode:
        return explicit_mode

    intent = str(graph_plan.get("intent") or "").strip().lower()
    if intent == "entity_summary":
        return "entity_summary"
    if intent == "neighborhood_lookup":
        return "neighborhood_summary"
    if intent == "relation_lookup":
        return "relation_evidence"
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
    graph_evidence = str(metadata.get("graph_evidence") or metadata.get("graph_summary") or "").strip()

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
    metadata_context: str,
) -> str:
    sections: list[str] = []
    if primary_context.strip():
        sections.append(f"[Primary evidence]\n{primary_context.strip()}")
    if supporting_context.strip():
        sections.append(f"[Supporting evidence]\n{supporting_context.strip()}")
    if metadata_context.strip():
        sections.append(f"[Metadata]\n{metadata_context.strip()}")
    return "\n\n".join(sections).strip()


async def kb_chat_retrieve_node(state: KbChatState) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    if str(state.get("retrieval_strategy") or "").strip().lower() == "skip":
        return {
            "retrieved_docs": [],
            "graph_primary_docs": [],
            "graph_supporting_docs": [],
            "primary_evidence_docs": [],
            "supporting_evidence_docs": [],
            "metadata_evidence_docs": [],
            "primary_context": "",
            "supporting_context": "",
            "metadata_context": "",
            "context": "",
            "retrieval_trace": {
                "retrieval_strategy": "skip",
                "text": {"skipped": True, "text_hits": 0},
                "graph": {"graph_used": False, "graph_hits": 0, "empty_reason": "skipped"},
                "final_hits": 0,
                "empty_reason": "skipped",
            },
        }

    emit_progress(
        stream_writer,
        node_id="retrieve",
        stage="retrieve",
        message="正在查找知识库内容",
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
        execution_plan.get("retrieval_strategy") or state.get("retrieval_strategy") or "parallel_fusion"
    ).strip().lower()
    final_top_k = int(context_plan.get("final_top_k") or 8)
    llm_reference_top_k = int(context_plan.get("llm_reference_top_k") or final_top_k)
    recall_k = int(vector_plan.get("recall_k") or final_top_k)
    lexical_k = int(lexical_plan.get("lexical_k") or final_top_k)
    graph_limit = int(graph_plan.get("limit") or final_top_k)
    graph_enabled = bool(graph_plan.get("enabled", True))
    graph_mode = _resolve_graph_mode_from_plan(graph_plan)
    context_budget = int(context_plan.get("budget_chars") or 9000)
    rerank_enabled = bool(settings.RERANK_ENABLED) and bool(rerank_plan.get("enabled"))
    question_type = str(state.get("question_type") or "definition_lookup").strip().lower()

    common_kwargs = {
        "team_id": state.get("team_id"),
        "knowledge_base_id": state.get("knowledge_base_id"),
        "category_id": state.get("category_id"),
        "log_prefix": "[User KB Retrieval]",
        "user_id": state.get("user_id"),
        "result_limit": final_top_k,
        "llm_reference_top_k": llm_reference_top_k,
        "context_budget": context_budget,
        "document_statuses": state.get("allowed_document_statuses"),
        "retrieval_version_mode": state.get("retrieval_version_mode"),
        "recall_k": recall_k,
        "lexical_k": lexical_k,
        "rerank_enabled": rerank_enabled,
    }

    async def _run_text_retrieval() -> dict[str, Any]:
        return await run_kb_channel_text_retrieval(
            query=query,
            semantic_queries=semantic_queries,
            lexical_terms=lexical_terms,
            **common_kwargs,
        )

    async def _run_graph_retrieval() -> dict[str, Any]:
        return await GraphRetriever(enabled=graph_enabled).retrieve(
            knowledge_base_id=int(state.get("knowledge_base_id") or 0),
            team_id=int(state.get("team_id") or 0),
            candidate_entities=candidate_entities,
            relation_pairs=list(state.get("relation_pairs") or []),
            relation_queries=list(state.get("relation_queries") or []),
            question_type=question_type,
            graph_mode=graph_mode,
            limit=graph_limit,
        )

    text_result: dict[str, Any]
    graph_result: dict[str, Any]
    text_result, graph_result = await asyncio.gather(_run_text_retrieval(), _run_graph_retrieval())

    text_docs = list(text_result.get("retrieved_docs") or [])
    graph_primary_docs = list(graph_result.get("graph_primary_docs") or [])
    graph_supporting_docs = list(graph_result.get("graph_supporting_docs") or [])
    merge_started_at = perf_counter()
    merged_docs = _merge_text_and_graph_docs(
        text_docs,
        graph_primary_docs,
        final_top_k=max(final_top_k, len(text_docs) + len(graph_primary_docs)),
    )
    primary_docs: list[dict[str, Any]] = []
    metadata_docs: list[dict[str, Any]] = []
    for doc in merged_docs:
        layer = _classify_evidence(doc, question_type=question_type)
        if layer == "primary":
            primary_docs.append(doc)
        else:
            metadata_docs.append(doc)
    reranked_primary_docs = (
        await rerank_retrieved_docs(query, primary_docs, final_top_k)
        if rerank_enabled
        else primary_docs[:final_top_k]
    )
    supporting_docs = graph_supporting_docs
    primary_context = _build_layer_context(reranked_primary_docs)
    supporting_context = _build_supporting_context(supporting_docs)
    metadata_context = _build_layer_context(metadata_docs)
    context = _compose_full_context(
        primary_context=primary_context,
        supporting_context=supporting_context,
        metadata_context=metadata_context,
    )
    merge_latency_ms = int((perf_counter() - merge_started_at) * 1000)
    if format_chat_history(state.get("chat_history") or [], max_messages=4):
        text_result["chat_history"] = state.get("chat_history") or []

    final_hits = len(reranked_primary_docs)
    text_trace = dict(text_result.get("retrieval_trace") or {})
    graph_trace = dict(graph_result.get("trace") or {})
    rerank_trace = dict(text_trace.get("rerank") or {})
    rerank_trace["enabled_for_primary_evidence"] = rerank_enabled
    rerank_trace["input_count"] = len(primary_docs)
    rerank_trace["output_count"] = len(reranked_primary_docs)
    trace = {
        "retrieval_strategy": retrieval_strategy,
        "text": {
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
        "rerank": rerank_trace,
        "final_hits": final_hits,
        "empty_reason": None if final_hits else "no_hits",
        "retrieval_complexity": state.get("retrieval_complexity"),
        "execution_plan": execution_plan,
        "total_latency_ms": text_trace.get("total_latency_ms"),
        "merge_latency_ms": merge_latency_ms,
        "primary_count": len(reranked_primary_docs),
        "supporting_count": len(supporting_docs),
        "metadata_count": len(metadata_docs),
        "graph_primary_count": len(graph_primary_docs),
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
                if (doc.get("metadata") or {}).get("source") in {"graph", "text_graph", "graph_summary", "graph_relation_summary"}
            ]
        ),
        "final_context_docs": len(reranked_primary_docs),
    }
    logger.info(
        "[KB Retrieve] done | strategy={} question_type={} semantic_queries={} lexical_terms={} candidate_entities={} relation_pairs={} relation_queries={} text_hits={} graph_hits={} graph_primary_count={} graph_supporting_count={} graph_empty_reason={} primary_count={} supporting_count={} metadata_count={} final_hits={} graph_evidence_count={}",
        retrieval_strategy,
        question_type,
        semantic_queries,
        lexical_terms,
        candidate_entities,
        list(state.get("relation_pairs") or []),
        list(state.get("relation_queries") or []),
        len(text_docs),
        graph_trace.get("graph_hits"),
        len(graph_primary_docs),
        len(supporting_docs),
        graph_trace.get("empty_reason"),
        len(reranked_primary_docs),
        len(supporting_docs),
        len(metadata_docs),
        final_hits,
        trace["graph_evidence_count"],
    )
    return {
        "retrieved_docs": reranked_primary_docs,
        "graph_primary_docs": graph_primary_docs,
        "graph_supporting_docs": supporting_docs,
        "reranked_primary_evidence_docs": reranked_primary_docs,
        "primary_evidence_docs": reranked_primary_docs,
        "supporting_evidence_docs": supporting_docs,
        "metadata_evidence_docs": metadata_docs,
        "primary_context": primary_context,
        "supporting_context": supporting_context,
        "metadata_context": metadata_context,
        "context": context,
        "retrieval_trace": trace,
    }
