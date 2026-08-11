"""单目标知识库检索、回答材料整理与一次无命中改写。"""

from __future__ import annotations

import hashlib
from typing import Any

from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.knowledge_qa.state import KnowledgeQaState
from app.services.kb_text_retrieval import run_kb_channel_text_retrieval


def _doc_identity(doc: dict[str, Any]) -> str:
    metadata = dict(doc.get("metadata") or {})
    parent_chunk_id = metadata.get("parent_chunk_id")
    if parent_chunk_id is not None:
        return f"parent:{parent_chunk_id}"
    chunk_id = metadata.get("document_chunk_id")
    if chunk_id is not None:
        return f"chunk:{chunk_id}"
    normalized_content = " ".join(str(doc.get("content") or "").split()).casefold()
    return "content:" + hashlib.sha1(normalized_content.encode("utf-8")).hexdigest()[:16]


def _dedupe_docs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        identity = _doc_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result


def _evidence_ref_id(doc: dict[str, Any]) -> str:
    metadata = dict(doc.get("metadata") or {})
    parent_chunk_id = metadata.get("parent_chunk_id")
    if parent_chunk_id is not None:
        return f"parent:{parent_chunk_id}"
    chunk_id = metadata.get("document_chunk_id")
    if chunk_id is not None:
        return f"chunk:{chunk_id}"
    return _doc_identity(doc)


def _build_evidence_item(doc: dict[str, Any], *, role: str) -> dict[str, Any] | None:
    content = str(doc.get("content") or "").strip()
    if not content:
        return None
    metadata = dict(doc.get("metadata") or {})
    return {
        "ref_id": _evidence_ref_id(doc),
        "role": role,
        "kind": "document_chunk",
        "content": content,
        "source": {
            "document_id": metadata.get("document_id"),
            "document_chunk_id": metadata.get("document_chunk_id"),
            "parent_chunk_id": metadata.get("parent_chunk_id"),
            "document_title": metadata.get("document_title"),
            "section_path": metadata.get("section_path"),
            "source_path": metadata.get("source_path"),
            "language": metadata.get("language"),
            "start_line": metadata.get("start_line"),
            "end_line": metadata.get("end_line"),
            "source_type": metadata.get("source") or "text",
        },
    }


def _apply_evidence_budget(
    items: list[dict[str, Any]], *, max_chars: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    used_chars = 0
    truncated = False
    for item in items:
        content = str(item.get("content") or "").strip()
        source = dict(item.get("source") or {})
        header_chars = len(str(source.get("document_title") or "")) + len(
            str(source.get("section_path") or "")
        )
        header_chars += len(str(source.get("source_path") or "")) + len(
            str(source.get("language") or "")
        )
        if max_chars > 0:
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


def _empty_metrics() -> dict[str, int]:
    return {
        "primary_count": 0,
        "supporting_count": 0,
        "text_hit_count": 0,
        "graph_hit_count": 0,
        "rerank_input_count": 0,
        "rerank_output_count": 0,
    }


async def knowledge_qa_retrieve_node(
    state: KnowledgeQaState,
    *,
    node_id: str = "retrieve_knowledge",
) -> dict[str, Any]:
    """执行一个目标的一组并行查询，并整理重排后的回答材料。"""

    if str(state.get("retrieval_strategy") or "").strip().lower() == "skip":
        return {
            "retrieval_result": {
                "status": "no_hits",
                "reason_code": "skipped",
                "evidence_items": [],
                "budget": {"max_chars": 0, "used_chars": 0, "truncated": False, "dropped_count": 0},
                "metrics": _empty_metrics(),
                "warnings": [],
            }
        }

    stream_writer = get_optional_stream_writer()
    emit_activity(
        stream_writer,
        workflow_id="knowledge_qa",
        node_id=node_id,
        stage="retrieve",
        message="正在查找知识库内容",
        display_stage="execute",
        display_title="🔍 查阅相关资料",
        activity_text="并行检索语义查询与精确短语",
    )
    goal = str(state.get("query") or "").strip()
    semantic_queries = [
        str(item).strip()
        for item in list(state.get("semantic_queries") or [])
        if str(item).strip()
    ]
    lexical_terms = [
        str(item).strip()
        for item in list(state.get("lexical_terms") or [])
        if str(item).strip()
    ]
    if not semantic_queries and not lexical_terms:
        raise ValueError("知识库检索缺少可执行查询")

    execution_plan = dict(state.get("retrieval_execution_plan") or {})
    channels = dict(execution_plan.get("channels") or {})
    vector_plan = dict(channels.get("vector") or {})
    lexical_plan = dict(channels.get("lexical") or {})
    rerank_plan = dict(execution_plan.get("rerank") or {})
    context_plan = dict(execution_plan.get("context") or {})
    final_top_k = int(context_plan.get("final_top_k") or 8)
    context_budget = int(context_plan.get("budget_chars") or 9000)

    provider_error: Exception | None = None
    try:
        text_result = await run_kb_channel_text_retrieval(
            query=str(state.get("normalized_query") or goal).strip(),
            semantic_queries=semantic_queries,
            lexical_terms=lexical_terms,
            team_id=state.get("team_id"),
            knowledge_base_id=state.get("knowledge_base_id"),
            category_id=state.get("category_id"),
            user_id=state.get("user_id"),
            result_limit=final_top_k,
            llm_reference_top_k=int(
                context_plan.get("llm_reference_top_k") or final_top_k
            ),
            context_budget=context_budget,
            document_statuses=list(state.get("allowed_document_statuses") or []),
            recall_k=int(vector_plan.get("recall_k") or final_top_k),
            lexical_k=int(lexical_plan.get("lexical_k") or final_top_k),
            rerank_enabled=bool(rerank_plan.get("enabled")),
        )
    except Exception as exc:
        provider_error = exc
        text_result = {
            "retrieved_docs": [],
            "kb_retrieval_status": "provider_error",
            "semantic_queries": semantic_queries[:3],
            "lexical_terms": lexical_terms[:3],
            "retrieval_trace": {},
        }

    current_docs = [
        dict(item)
        for item in list(text_result.get("retrieved_docs") or [])
        if isinstance(item, dict)
    ]
    accumulated_docs = _dedupe_docs(
        [
            *current_docs,
            *[
                dict(item)
                for item in list(state.get("accumulated_candidate_docs") or [])
                if isinstance(item, dict)
            ],
        ]
    )
    executed_semantic_queries = [
        str(item).strip()
        for item in list(text_result.get("semantic_queries") or semantic_queries)
        if str(item).strip()
    ]
    executed_lexical_terms = [
        str(item).strip()
        for item in list(text_result.get("lexical_terms") or lexical_terms)
        if str(item).strip()
    ]
    evidence_items: list[dict[str, Any]] = []
    for doc in accumulated_docs:
        item = _build_evidence_item(doc, role="primary")
        if item is not None:
            evidence_items.append(item)
    evidence_items, budget = _apply_evidence_budget(
        evidence_items, max_chars=context_budget
    )
    primary_count = sum(item.get("role") == "primary" for item in evidence_items)
    supporting_count = 0

    attempt_number = int(state.get("query_plan_attempt") or 1)
    should_replan = (
        provider_error is None
        and primary_count == 0
        and attempt_number < 2
        and not state.get("replan_exhausted")
    )
    previous_used_queries = [
        str(item).strip()
        for item in list((state.get("retrieval_feedback") or {}).get("used_queries") or [])
        if str(item).strip()
    ]
    used_queries = list(
        dict.fromkeys(
            [*previous_used_queries, *executed_semantic_queries, *executed_lexical_terms]
        )
    )
    retrieval_feedback = {
        "goal": goal,
        "reason_code": (
            text_result.get("kb_retrieval_status")
            if primary_count == 0
            else None
        ),
        "used_queries": used_queries,
        "attempt": attempt_number,
    }
    trace = dict(text_result.get("retrieval_trace") or {})
    rerank_trace = dict(trace.get("rerank") or {})
    retrieval_attempts = [
        *[
            dict(item)
            for item in list(state.get("retrieval_attempts") or [])
            if isinstance(item, dict)
        ],
        {
            "attempt": attempt_number,
            "semantic_queries": executed_semantic_queries,
            "lexical_terms": executed_lexical_terms,
            "hit_count": len(current_docs),
            "retrieval_status": "found" if primary_count else "no_hits",
        },
    ]
    if provider_error is not None:
        status = "provider_error"
        reason_code = "provider_error"
    elif should_replan:
        status = "replan_required"
        reason_code = text_result.get("kb_retrieval_status") or "no_hits"
    elif primary_count:
        status = "found"
        reason_code = None
    else:
        status = "no_hits"
        reason_code = (
            text_result.get("kb_retrieval_status")
            if text_result.get("kb_retrieval_status") != "ok"
            else "no_hits"
        )
    warnings = []
    if provider_error is not None:
        warnings.append(
            {"code": "RETRIEVAL_PROVIDER_ERROR", "message": "知识库检索服务暂时不可用。"}
        )
    return {
        "should_replan": should_replan,
        "retrieval_feedback": retrieval_feedback,
        "retrieval_attempts": retrieval_attempts,
        "accumulated_candidate_docs": accumulated_docs,
        "accumulated_evidence_items": evidence_items,
        "retrieval_result": {
            "status": status,
            "reason_code": reason_code,
            "evidence_items": evidence_items,
            "attempt_count": len(retrieval_attempts),
            "budget": budget,
            "metrics": {
                "primary_count": primary_count,
                "supporting_count": supporting_count,
                "text_hit_count": len(accumulated_docs),
                "graph_hit_count": 0,
                "rerank_input_count": int(trace.get("merged_candidate_count") or 0),
                "rerank_output_count": int(rerank_trace.get("output_count") or len(current_docs)),
            },
            "warnings": warnings,
        },
    }
