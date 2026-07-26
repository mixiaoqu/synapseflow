"""Build structured diagnostics from completed Agent runs."""

from __future__ import annotations

from typing import Any

from loguru import logger


class AgentRunTraceBuilder:
    """Convert run state into trace payloads and review-log messages."""

    @staticmethod
    def build_log_trace_payload(
        *,
        state: dict[str, Any],
        result: dict[str, Any],
        retrieved_docs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        retrieval_trace = (
            dict(result.get("retrieval_trace") or {})
            if isinstance(result.get("retrieval_trace"), dict)
            else {}
        )
        text_trace = (
            dict(retrieval_trace.get("text") or {})
            if isinstance(retrieval_trace.get("text"), dict)
            else {}
        )
        graph_trace = (
            dict(retrieval_trace.get("graph") or {})
            if isinstance(retrieval_trace.get("graph"), dict)
            else {}
        )
        rerank_trace = (
            dict(retrieval_trace.get("rerank") or {})
            if isinstance(retrieval_trace.get("rerank"), dict)
            else {}
        )
        retrieval_funnel = (
            text_trace.get("funnel") if isinstance(text_trace.get("funnel"), dict) else {}
        )
        semantic_query_stats = [
            item
            for item in list(retrieval_funnel.get("semantic_queries") or [])
            if isinstance(item, dict)
        ]
        lexical_term_stats = [
            item
            for item in list(retrieval_funnel.get("lexical_terms") or [])
            if isinstance(item, dict)
        ]

        def _string_items(value: Any) -> list[str]:
            return [str(item).strip() for item in list(value or []) if str(item or "").strip()]

        semantic_queries = _string_items(result.get("semantic_queries")) or _string_items(
            state.get("semantic_queries")
        )
        lexical_terms = _string_items(result.get("lexical_terms")) or _string_items(
            state.get("lexical_terms")
        )
        candidate_entities = _string_items(result.get("candidate_entities")) or _string_items(
            state.get("candidate_entities")
        )
        if not semantic_queries:
            semantic_queries = [
                str(item.get("query") or "").strip()
                for item in semantic_query_stats
                if str(item.get("query") or "").strip()
            ]
        if not lexical_terms:
            lexical_terms = [
                str(item.get("query") or "").strip()
                for item in lexical_term_stats
                if str(item.get("query") or "").strip()
            ]
        text_hit_count = int(text_trace.get("text_hits") or 0)
        graph_hit_count = int(graph_trace.get("graph_hits") or 0)
        merged_count = int(
            retrieval_trace.get("merged_pool_count")
            or text_trace.get("merged_candidate_count")
            or 0
        )
        final_context_count = int(retrieval_trace.get("final_context_docs") or len(retrieved_docs))
        rerank_count = int(rerank_trace.get("output_count") or final_context_count)

        def _query_stat_total(items: list[dict[str, Any]]) -> int:
            return sum(int(item.get("chunk_count") or 0) for item in items)

        def _source_status(*, query_count: int, recall_count: int, empty_reason: Any = None) -> str:
            reason = str(empty_reason or "").strip()
            if reason in {"skipped", "disabled"}:
                return reason
            if query_count <= 0:
                return "skipped"
            if recall_count <= 0:
                return reason or "no_hits"
            return "normal"

        def _source_type(metadata: dict[str, Any]) -> str:
            source = str(metadata.get("source") or "").strip().lower()
            if source in {"hybrid", "text_graph"}:
                return "hybrid"
            if source in {
                "graph",
                "graph_entity",
                "graph_relation",
                "graph_relation_evidence",
                "graph_path",
            }:
                return "graph"
            if source == "lexical":
                return "lexical"
            return "vector"

        def _score(metadata: dict[str, Any]) -> float | None:
            raw_score = metadata.get("rerank_score")
            if raw_score is None:
                raw_score = metadata.get("score")
            if raw_score is None:
                return None
            try:
                return round(float(raw_score), 3)
            except (TypeError, ValueError):
                return None

        def _doc_identity(doc: dict[str, Any], metadata: dict[str, Any]) -> str:
            return str(
                metadata.get("document_chunk_id")
                or metadata.get("chunk_id")
                or metadata.get("document_id")
                or doc.get("content")
                or ""
            )

        def _build_trace_docs(raw_docs: list[Any]) -> list[dict[str, Any]]:
            docs: list[dict[str, Any]] = []
            for index, doc in enumerate(raw_docs, start=1):
                if not isinstance(doc, dict):
                    continue
                metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
                title = str(metadata.get("document_title") or f"候选片段 #{index}")
                source_type = _source_type(metadata)
                docs.append(
                    {
                        "rank": int(doc.get("rank") or index),
                        "original_rank": index,
                        "title": title,
                        "section_path": str(metadata.get("section_path") or ""),
                        "source_type": source_type,
                        "source_label": {
                            "hybrid": "Hybrid",
                            "lexical": "Lexical",
                            "graph": "Graph",
                            "vector": "Vector",
                        }[source_type],
                        "score": _score(metadata),
                        "selected": False,
                        "identity": _doc_identity(doc, metadata),
                        "content": str(doc.get("content") or ""),
                        "metadata": dict(metadata),
                    }
                )
            return docs

        final_context_docs = _build_trace_docs(
            list(result.get("primary_evidence_docs") or retrieved_docs or [])
        )
        selected_identities = {
            str(doc.get("identity") or "")
            for doc in final_context_docs
            if str(doc.get("identity") or "")
        }
        ranked_candidates = _build_trace_docs(
            list(
                result.get("reranked_primary_evidence_docs")
                or result.get("primary_evidence_docs")
                or retrieved_docs
                or []
            )
        )
        for doc in ranked_candidates:
            doc["selected"] = bool(
                doc.get("identity") and doc.get("identity") in selected_identities
            )

        return {
            "query_clues": {
                "semantic_queries": semantic_queries,
                "lexical_terms": lexical_terms,
                "candidate_entities": candidate_entities,
            },
            "source_summary": {
                "vector": {
                    "query_count": len(semantic_queries),
                    "recall_count": _query_stat_total(semantic_query_stats),
                    "candidate_count": text_hit_count,
                    "status": _source_status(
                        query_count=len(semantic_queries),
                        recall_count=_query_stat_total(semantic_query_stats),
                        empty_reason=text_trace.get("empty_reason"),
                    ),
                },
                "lexical": {
                    "query_count": len(lexical_terms),
                    "recall_count": _query_stat_total(lexical_term_stats),
                    "candidate_count": text_hit_count,
                    "status": _source_status(
                        query_count=len(lexical_terms),
                        recall_count=_query_stat_total(lexical_term_stats),
                        empty_reason=text_trace.get("empty_reason"),
                    ),
                },
                "graph": {
                    "query_count": len(candidate_entities),
                    "recall_count": graph_hit_count,
                    "candidate_count": int(
                        retrieval_trace.get("graph_primary_count") or graph_hit_count
                    ),
                    "status": _source_status(
                        query_count=len(candidate_entities),
                        recall_count=graph_hit_count,
                        empty_reason=graph_trace.get("empty_reason"),
                    ),
                },
            },
            "funnel": {
                "recall_total": text_hit_count + graph_hit_count,
                "duplicates_folded": int(retrieval_trace.get("duplicates_folded") or 0),
                "merged_count": merged_count,
                "rerank_count": rerank_count,
                "final_context_count": final_context_count,
            },
            "branch_summaries": {
                "vector": [
                    {
                        "query": str(item.get("query") or "").strip(),
                        "chunk_count": int(item.get("chunk_count") or 0),
                    }
                    for item in semantic_query_stats
                    if str(item.get("query") or "").strip()
                ],
                "lexical": [
                    {
                        "query": str(item.get("query") or "").strip(),
                        "chunk_count": int(item.get("chunk_count") or 0),
                    }
                    for item in lexical_term_stats
                    if str(item.get("query") or "").strip()
                ],
                "graph": [
                    {
                        "query": entity,
                        "chunk_count": graph_hit_count,
                    }
                    for entity in candidate_entities
                ],
            },
            "ranked_candidates": ranked_candidates,
            "final_context_docs": final_context_docs,
            "supporting_evidence_docs": _build_trace_docs(
                list(result.get("supporting_evidence_docs") or [])
            ),
            "debug": {
                "retrieval_trace": (retrieval_trace),
                "rewrite_trace": (
                    dict(result.get("rewrite_trace") or {})
                    if isinstance(result.get("rewrite_trace"), dict)
                    else {}
                ),
            },
        }

    @staticmethod
    def _build_retrieval_review_log_message(
        *,
        state: dict[str, Any],
        result: dict[str, Any],
        total_latency_ms: int,
    ) -> str:
        retrieval_trace = dict(result.get("retrieval_trace") or {})
        text_trace = dict(retrieval_trace.get("text") or {})
        graph_trace = dict(retrieval_trace.get("graph") or {})
        rerank_trace = dict(retrieval_trace.get("rerank") or {})
        rewrite_trace = dict(result.get("rewrite_trace") or {})
        route_trace = dict(result.get("route_trace") or {})
        plan_trace = dict(result.get("plan_trace") or {})
        answer_trace = dict(result.get("answer_trace") or {})
        semantic_queries = list(result.get("semantic_queries") or [])
        lexical_terms = list(result.get("lexical_terms") or [])
        candidate_entities = list(result.get("candidate_entities") or [])

        def _format_list(values: list[Any], *, empty_text: str = "(none)") -> str:
            items = [str(value).strip() for value in values if str(value).strip()]
            return ", ".join(items) if items else empty_text

        def _format_queries(values: list[str]) -> str:
            if not values:
                return "  (none)"
            return "\n".join(f"  {index + 1}. {value}" for index, value in enumerate(values[:3]))

        text_stage_rerank_trace = dict(rerank_trace.get("text_stage") or {})
        text_stage_rerank_enabled = text_stage_rerank_trace.get("enabled")
        if text_stage_rerank_enabled is None:
            text_stage_rerank_enabled = text_stage_rerank_trace.get("rerank_enabled")

        return (
            "[问答审查日志 #{}] {}\n"
            "问题：{}\n"
            "会话：{}\n"
            "团队/知识库：{} / {}\n"
            "\n"
            "1. 问题分析\n"
            "- question_type: {}\n"
            "- retrieval_required: {}\n"
            "- retrieval_complexity: {}\n"
            "- reason: {}\n"
            "- route_latency_ms: {}\n"
            "- plan_latency_ms: {}\n"
            "\n"
            "2. 检索改写\n"
            "- 原问题: {}\n"
            "- 向量语义查询:\n{}\n"
            "- 关键词: {}\n"
            "- candidate_entities: {}\n"
            "- rewrite_latency_ms: {}\n"
            "\n"
            "3. 检索执行\n"
            "- retrieval_mode: {}\n"
            "- semantic_query_count: {}\n"
            "- lexical_term_count: {}\n"
            "- recall_k: {}\n"
            "- lexical_k: {}\n"
            "- text_hits: {}\n"
            "- graph_used: {}\n"
            "- graph_hits: {}\n"
            "- final_context_docs: {}\n"
            "- text_stage_rerank_enabled: {}\n"
            "- final_rerank_enabled: {}\n"
            "- final_rerank_input_count: {}\n"
            "- final_rerank_output_count: {}\n"
            "- final_rerank_latency_ms: {}\n"
            "- empty_reason: {}\n"
            "- retrieval_latency_ms: {}\n"
            "- merge_latency_ms: {}\n"
            "\n"
            "4. 答案生成\n"
            "- answer_status: {}\n"
            "- confidence: {}\n"
            "- answer_latency_ms: {}\n"
            "- total_latency_ms: {}\n"
            "\n"
            "5. 审查信息\n"
            "- feedback: {}\n"
            "- suggested_review_label: {}\n"
            "- review_label: {}\n"
        ).format(
            result.get("log_id") or "-",
            result.get("created_at") or "-",
            str(result.get("query") or state.get("query") or ""),
            result.get("session_id") or state.get("session_id") or "-",
            result.get("team_name") or result.get("team_id") or state.get("team_id") or "-",
            result.get("knowledge_base_name")
            or result.get("knowledge_base_id")
            or state.get("knowledge_base_id")
            or "-",
            result.get("question_type") or state.get("question_type") or "-",
            (
                result.get("retrieval_required")
                if result.get("retrieval_required") is not None
                else state.get("retrieval_required")
            ),
            result.get("retrieval_complexity") or state.get("retrieval_complexity") or "-",
            result.get("route_reason") or result.get("reason") or state.get("route_reason") or "-",
            int(route_trace.get("latency_ms") or 0),
            int(plan_trace.get("latency_ms") or 0),
            str(result.get("query") or state.get("query") or ""),
            _format_queries([str(query) for query in semantic_queries if str(query).strip()]),
            _format_list(lexical_terms),
            _format_list(candidate_entities),
            int(rewrite_trace.get("latency_ms") or 0),
            str(retrieval_trace.get("retrieval_mode") or state.get("retrieval_mode") or "-"),
            int(text_trace.get("semantic_query_count") or len(semantic_queries) or 0),
            int(text_trace.get("lexical_term_count") or len(lexical_terms) or 0),
            int(text_trace.get("recall_k") or 0),
            int(text_trace.get("lexical_k") or 0),
            int(text_trace.get("text_hits") or text_trace.get("raw_candidate_count") or 0),
            bool(graph_trace.get("graph_used")),
            int(graph_trace.get("graph_hits") or 0),
            int(
                retrieval_trace.get("final_context_docs") or retrieval_trace.get("final_hits") or 0
            ),
            bool(text_stage_rerank_enabled),
            bool(rerank_trace.get("enabled")),
            int(rerank_trace.get("input_count") or 0),
            int(rerank_trace.get("output_count") or 0),
            int(rerank_trace.get("latency_ms") or 0),
            retrieval_trace.get("empty_reason") or graph_trace.get("empty_reason") or "-",
            int(
                text_trace.get("latency_ms")
                or retrieval_trace.get("text_retrieval_latency_ms")
                or 0
            ),
            int(retrieval_trace.get("merge_latency_ms") or 0),
            result.get("answer_status") or "-",
            answer_trace.get("confidence") or "-",
            int(answer_trace.get("latency_ms") or 0),
            total_latency_ms,
            result.get("feedback_value") or "(none)",
            result.get("suggested_review_label") or "(none)",
            result.get("review_label") or "（未审核）",
        )

    @staticmethod
    def log_retrieval_review(
        *,
        state: dict[str, Any],
        result: dict[str, Any],
        total_latency_ms: int,
    ) -> None:
        message = AgentRunTraceBuilder._build_retrieval_review_log_message(
            state=state,
            result=result,
            total_latency_ms=total_latency_ms,
        )
        if message:
            logger.bind(kb_review_log=True).info(message)

