"""Rewrite and entity extraction node for knowledge-base chat."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from loguru import logger

from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.states import KnowledgeQaState
from app.services.kb_query_rewrite import build_kb_chat_retrieval_queries


async def build_kb_chat_rewrite(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None,
    memory_summary: str | None,
    page_context: dict[str, Any] | None,
    rewrite_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    plan = dict(rewrite_plan or {})
    question_type = str(plan.get("question_type") or "entity_lookup").strip().lower()
    retrieval_complexity = str(plan.get("retrieval_complexity") or "standard").strip().lower()

    started_at = perf_counter()
    rewrite_result = await build_kb_chat_retrieval_queries(
        query,
        chat_history=chat_history or [],
        memory_summary=memory_summary,
        runtime_context=page_context or {},
        question_type=question_type,
        retrieval_label=retrieval_complexity,
    )
    semantic_queries = list(rewrite_result.get("semantic_queries") or [])
    lexical_terms = list(rewrite_result.get("lexical_terms") or [])
    candidate_entities = list(rewrite_result.get("candidate_entities") or [])
    relation_pairs = list(rewrite_result.get("relation_pairs") or [])
    relation_queries = list(rewrite_result.get("relation_queries") or [])
    target_attributes = [
        str(item).strip()
        for item in list(rewrite_result.get("target_attributes") or [])
        if str(item).strip()
    ]
    entity_constraints = (
        dict(rewrite_result.get("entity_constraints") or {})
        if isinstance(rewrite_result.get("entity_constraints"), dict)
        else {}
    )
    trace = {
        "used": True,
        "engine": "llm",
        "policy": question_type,
        "retrieval_complexity": retrieval_complexity,
        "semantic_query_count": len(semantic_queries),
        "lexical_term_count": len(lexical_terms),
        "entity_count": len(candidate_entities),
        "relation_pair_count": len(relation_pairs),
        "relation_query_count": len(relation_queries),
        "fallback_used": False,
        "latency_ms": int((perf_counter() - started_at) * 1000),
    }
    logger.info(
        "[KB Rewrite] done | question_type={} retrieval_complexity={} semantic_queries={} lexical_terms={} candidate_entities={} relation_pairs={} relation_queries={} latency_ms={}",
        question_type,
        retrieval_complexity,
        semantic_queries,
        lexical_terms,
        candidate_entities,
        relation_pairs,
        relation_queries,
        trace["latency_ms"],
    )
    return {
        "semantic_queries": semantic_queries,
        "lexical_terms": lexical_terms,
        "candidate_entities": candidate_entities,
        "relation_pairs": relation_pairs,
        "relation_queries": relation_queries,
        "target_attributes": target_attributes,
        "entity_constraints": entity_constraints,
        "rewrite_trace": trace,
    }


async def kb_chat_rewrite_query_node(
    state: KnowledgeQaState,
    *,
    node_id: str = "rewrite_query",
) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    if str(state.get("retrieval_strategy") or "").strip().lower() == "skip":
        trace = {
            "used": False,
            "engine": "skip",
            "semantic_query_count": 0,
            "lexical_term_count": 0,
            "entity_count": 0,
        }
        return {
            "semantic_queries": [],
            "lexical_terms": [],
            "candidate_entities": [],
            "relation_pairs": [],
            "relation_queries": [],
            "target_attributes": [],
            "entity_constraints": {},
            "rewrite_trace": trace,
        }
    emit_activity(
        stream_writer,
        workflow_id="knowledge_qa",
        node_id=node_id,
        stage="rewrite",
        message="正在整理检索线索",
        display_stage="execute",
        display_title="🔍 查阅相关资料",
        activity_text="正在整理资料查找线索",
    )
    return await build_kb_chat_rewrite(
        str(state.get("query") or ""),
        chat_history=list(state.get("chat_history") or []),
        memory_summary=state.get("memory_summary"),
        page_context=dict(state.get("page_context") or {}),
        rewrite_plan=((state.get("retrieval_execution_plan") or {}).get("rewrite") or {}),
    )
