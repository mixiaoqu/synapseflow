"""Text and graph retrieval node for kb_chat_v2."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatV2State
from app.services.chat_memory import format_chat_history
from app.services.kb_graph_retrieval import GraphRetriever
from app.services.kb_text_retrieval import (
    run_kb_text_retrieval,
    run_multi_query_kb_text_retrieval,
)


def _doc_key(doc: dict[str, Any]) -> tuple[Any, ...]:
    metadata = dict(doc.get("metadata") or {})
    document_chunk_id = metadata.get("document_chunk_id")
    if document_chunk_id is None:
        raise ValueError("retrieved doc missing document_chunk_id")
    return ("chunk", int(document_chunk_id))


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


async def kb_chat_v2_retrieve_node(state: KbChatV2State) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    if state.get("retrieval_required") is False:
        return {
            "retrieved_docs": [],
            "context": "",
            "retrieval_trace": {
                "retrieval_mode": "skip",
                "text": {"skipped": True, "text_hits": 0},
                "graph": {"graph_used": False, "graph_hits": 0, "empty_reason": "skipped"},
                "global": {"enabled": False, "empty_reason": "skipped", "fallback": None},
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
    text_queries = [
        str(item).strip()
        for item in list(state.get("text_queries") or [])
        if str(item or "").strip()
    ] or [query]

    execution_plan = dict(state.get("retrieval_execution_plan") or {})
    channels = dict(execution_plan.get("channels") or {})
    vector_plan = dict(channels.get("vector") or {})
    lexical_plan = dict(channels.get("lexical") or {})
    graph_plan = dict(channels.get("graph") or {})
    rerank_plan = dict(execution_plan.get("rerank") or {})
    context_plan = dict(execution_plan.get("context") or {})
    retrieval_mode = str(execution_plan.get("retrieval_mode") or "local_hybrid").strip().lower()
    community_plan = dict(channels.get("community") or {})
    final_top_k = int(context_plan.get("final_top_k") or 8)
    llm_reference_top_k = int(context_plan.get("llm_reference_top_k") or final_top_k)
    recall_k = int(vector_plan.get("recall_k") or final_top_k)
    lexical_k = int(lexical_plan.get("recall_k") or final_top_k)
    graph_limit = int(graph_plan.get("limit") or final_top_k)
    context_budget = int(context_plan.get("budget_chars") or 9000)
    rerank_enabled = bool(rerank_plan.get("enabled", True))

    common_kwargs = {
        "team_id": state.get("team_id"),
        "knowledge_base_id": state.get("knowledge_base_id"),
        "category_id": state.get("category_id"),
        "log_prefix": "[User KB Retrieval V2]",
        "user_id": state.get("user_id"),
        "result_limit": final_top_k,
        "llm_reference_top_k": llm_reference_top_k,
        "context_budget": context_budget,
        "document_statuses": state.get("allowed_document_statuses"),
        "retrieval_version_mode": state.get("retrieval_version_mode"),
        "retrieval_mode": "hybrid",
        "recall_k": recall_k,
        "lexical_k": lexical_k,
        "rerank_enabled": rerank_enabled,
    }
    text_result: dict[str, Any] = {
        "retrieved_docs": [],
        "context": "",
        "retrieval_trace": {
            "text_retrieval_latency_ms": 0,
            "raw_candidate_count": 0,
            "merged_candidate_count": 0,
            "total_latency_ms": 0,
            "rerank": {},
        },
    }
    graph_result: dict[str, Any] = {
        "retrieved_docs": [],
        "trace": {
            "graph_used": False,
            "graph_hits": 0,
            "empty_reason": "skipped",
            "latency_ms": 0,
        },
    }
    text_docs: list[dict[str, Any]] = []
    graph_docs: list[dict[str, Any]] = []
    merged_docs: list[dict[str, Any]] = []
    context = ""
    merge_latency_ms = 0

    if retrieval_mode == "graph_first":
        graph_result = await GraphRetriever().retrieve(
            candidate_entities=list(state.get("candidate_entities") or []),
            knowledge_base_id=int(state.get("knowledge_base_id") or 0),
            team_id=int(state.get("team_id") or 0),
            limit=graph_limit,
        )
        graph_docs = list(graph_result.get("retrieved_docs") or [])
        if graph_docs:
            merged_docs = graph_docs[:final_top_k]
            context = _build_context(merged_docs)
        else:
            if len(text_queries) > 1:
                text_result = await run_multi_query_kb_text_retrieval(
                    query=query,
                    retrieval_queries=text_queries,
                    **common_kwargs,
                )
            else:
                text_result = await run_kb_text_retrieval(query=text_queries[0], **common_kwargs)
            text_docs = list(text_result.get("retrieved_docs") or [])
            merged_docs = text_docs[:final_top_k]
            context = str(text_result.get("context") or "")
    else:
        if len(text_queries) > 1:
            text_result = await run_multi_query_kb_text_retrieval(
                query=query,
                retrieval_queries=text_queries,
                **common_kwargs,
            )
        else:
            text_result = await run_kb_text_retrieval(query=text_queries[0], **common_kwargs)
        text_docs = list(text_result.get("retrieved_docs") or [])
        graph_result = await GraphRetriever().retrieve(
            candidate_entities=list(state.get("candidate_entities") or []),
            knowledge_base_id=int(state.get("knowledge_base_id") or 0),
            team_id=int(state.get("team_id") or 0),
            limit=graph_limit,
        )
        graph_docs = list(graph_result.get("retrieved_docs") or [])
        merge_started_at = perf_counter()
        merged_docs = _merge_text_and_graph_docs(text_docs, graph_docs, final_top_k=final_top_k)
        context = _build_context(merged_docs) or str(text_result.get("context") or "")
        merge_latency_ms = int((perf_counter() - merge_started_at) * 1000)
        if format_chat_history(state.get("chat_history") or [], max_messages=4):
            text_result["chat_history"] = state.get("chat_history") or []

    final_hits = len(merged_docs)
    text_trace = dict(text_result.get("retrieval_trace") or {})
    graph_trace = dict(graph_result.get("trace") or {})
    rerank_trace = dict(text_trace.get("rerank") or {})
    trace = {
        "retrieval_mode": retrieval_mode,
        "text": {
            "text_query_count": len(text_queries),
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
            "skipped": retrieval_mode == "graph_first" and bool(graph_docs),
        },
        "graph": graph_trace,
        "global": {
            "enabled": bool(community_plan.get("enabled")),
            "empty_reason": (
                "community_summary_layer_unavailable"
                if retrieval_mode == "global_priority"
                else "skipped" if retrieval_mode == "text_hybrid" else None
            ),
            "fallback": "local_hybrid" if retrieval_mode == "global_priority" else None,
        },
        "rerank": rerank_trace,
        "final_hits": final_hits,
        "empty_reason": None if final_hits else "no_hits",
        "retrieval_complexity": state.get("retrieval_complexity"),
        "execution_plan": execution_plan,
        "total_latency_ms": text_trace.get("total_latency_ms"),
        "merge_latency_ms": merge_latency_ms,
        "text_evidence_count": len(
            [doc for doc in merged_docs if (doc.get("metadata") or {}).get("source") != "graph"]
        ),
        "graph_evidence_count": len(
            [
                doc
                for doc in merged_docs
                if (doc.get("metadata") or {}).get("source") in {"graph", "text_graph"}
            ]
        ),
        "final_context_docs": len(merged_docs),
    }
    if retrieval_mode == "graph_first" and graph_docs:
        trace["text"]["empty_reason"] = "graph_hits"
        trace["text"]["text_hits"] = 0
        trace["text"]["skipped"] = True
    if retrieval_mode == "global_priority":
        trace["global"]["empty_reason"] = "community_summary_layer_unavailable"
        trace["global"]["fallback"] = "local_hybrid"
    return {
        "retrieved_docs": merged_docs,
        "context": context,
        "retrieval_trace": trace,
    }
