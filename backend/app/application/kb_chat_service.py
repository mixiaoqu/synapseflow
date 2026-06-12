"""Application service for end-user knowledge-base chat."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable

from loguru import logger

from app.agents.runtime import AgentEventType
from app.application.agent_service import BaseAgentService
from app.application.stream_events import (
    emit_complete,
    emit_error,
    emit_event,
    emit_node_complete,
    emit_node_start,
    emit_progress,
    emit_start,
)
from app.application.workflow_meta import get_node_label
from app.core.config.settings import settings
from app.db.session import AsyncSessionLocal
from app.db.models import ContentRiskLog
from app.repositories.content_risk_log_repository import ContentRiskLogRepository
from app.repositories.kb_chat_log_repository import KbChatLogRepository
from app.services.chat_memory import (
    ChatMemoryContext,
    ChatMemoryStore,
    DatabaseChatMemoryStore,
)
from app.services.content_risk_detection_service import (
    ContentRiskDetectionResult,
    get_content_risk_detection_service,
)
from app.services.document_lifecycle import RETRIEVAL_VERSION_LIVE, VISIBLE_ASK_DOCUMENT_STATUSES

if TYPE_CHECKING:
    from app.models.schemas.kb_chat import (
        KbChatRequest,
        KbChatResponse,
        KbChatSessionDetail,
        KbChatSessionSummary,
    )


class KbChatService(BaseAgentService):
    """Encapsulates end-user knowledge-base chat orchestration."""

    def __init__(
        self,
        llm_factory: Callable[[], Any] | None = None,
        graph: Any | None = None,
        memory_store: ChatMemoryStore | None = None,
        content_risk_detection_service: Any | None = None,
        workflow_id: str | None = None,
    ):
        self._llm_factory = llm_factory
        self._graph = graph
        self._workflow_id = self._normalize_workflow_id(workflow_id or settings.KB_CHAT_WORKFLOW)
        self._memory_store = memory_store or DatabaseChatMemoryStore()
        self._content_risk_detection_service = (
            content_risk_detection_service or get_content_risk_detection_service()
        )

    @staticmethod
    def _normalize_workflow_id(value: str | None) -> str:
        return "kb_chat"

    def build_initial_state(
        self,
        request: "KbChatRequest",
        *,
        user_id: int | None,
        session_id: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
        memory_summary: str | None = None,
    ) -> dict[str, Any]:
        """Build pipeline input state from the request payload."""

        resolved_session_id = session_id or request.session_id or self._new_run_id()
        history = list(chat_history or [])
        context = self.build_context(
            user_id=user_id,
            team_id=getattr(request, "team_id", None),
            knowledge_base_id=request.knowledge_base_id,
            category_id=getattr(request, "category_id", None),
            request_id=resolved_session_id,
            messages=history,
            metadata={"workflow": self._workflow_id},
        )
        state = self.build_state(
            context,
            {
                "workflow_id": self._workflow_id,
                "session_id": resolved_session_id,
                "query": request.query,
                "product_id": getattr(request, "product_id", None),
                "project_id": getattr(request, "project_id", None),
                "project_app_id": getattr(request, "project_app_id", None),
                "external_user_id": getattr(request, "external_user_id", None),
                "external_user_name": getattr(request, "external_user_name", None),
                "assistant_id": getattr(request, "assistant_id", None),
                "assistant_name": getattr(request, "assistant_name", None),
                "assistant_welcome_message": getattr(
                    request,
                    "assistant_welcome_message",
                    None,
                ),
                "assistant_placeholder_text": getattr(
                    request,
                    "assistant_placeholder_text",
                    None,
                ),
                "assistant_llm_model_key": getattr(
                    request,
                    "assistant_llm_model_key",
                    None,
                ),
                "assistant_persona_prompt": getattr(
                    request,
                    "assistant_persona_prompt",
                    None,
                ),
                "assistant_rule_template": getattr(
                    request,
                    "assistant_rule_template",
                    None,
                ),
                "assistant_suggested_prompts": list(
                    getattr(request, "assistant_suggested_prompts", None) or []
                ),
                "page_context": dict(getattr(request, "page_context", None) or {}),
                "page_config": dict(getattr(request, "page_config", None) or {}),
                "knowledge_base_ids": list(getattr(request, "knowledge_base_ids", None) or []),
                "chat_history": history,
                "memory_summary": memory_summary,
                "retrieval_execution_plan": {},
                "semantic_queries": [],
                "lexical_terms": [],
                "candidate_entities": [],
                "relation_pairs": [],
                "relation_queries": [],
                "target_attributes": [],
                "entity_constraints": {},
                "allowed_document_statuses": list(
                    getattr(request, "allowed_document_statuses", None)
                    or VISIBLE_ASK_DOCUMENT_STATUSES
                ),
                "retrieval_version_mode": (
                    getattr(request, "retrieval_version_mode", None) or RETRIEVAL_VERSION_LIVE
                ),
                "retrieved_docs": [],
                "context": "",
                "answer": "",
                "question_type": None,
                "retrieval_complexity": "standard",
                "retrieval_required": True,
                "route_reason": "",
                "route_trace": {},
                "plan_trace": {},
                "rewrite_trace": {},
                "retrieval_trace": {},
                "retrieval_evaluation": {},
                "evaluate_trace": {},
                "graph_enabled": False,
                "graph_intent": None,
                "graph_mode": None,
                "graph_requires_grounding": False,
                "graph_max_hops": 0,
                "graph_budget": 0,
                "fusion_policy": None,
                "graph_boost": None,
                "reranked_primary_evidence_docs": [],
                "primary_evidence_docs": [],
                "supporting_evidence_docs": [],
                "metadata_evidence_docs": [],
                "primary_context": "",
                "supporting_context": "",
                "metadata_context": "",
                "answer_status": "",
                "answer_trace": {},
            },
        )
        return state

    def _get_graph(self) -> Any:
        if self._graph is None:
            from app.agents.graphs.kb_chat_graph import create_kb_chat_graph

            self._graph = create_kb_chat_graph(llm_factory=self._llm_factory)
        return self._graph

    async def _load_memory_context(
        self,
        *,
        user_id: int | None,
        session_id: str,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> ChatMemoryContext:
        return await self._memory_store.load_context(
            user_id=user_id,
            session_id=session_id,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
        )

    async def _prepare_state(
        self,
        request: "KbChatRequest",
        *,
        user_id: int | None,
    ) -> dict[str, Any]:
        resolved_session_id = request.session_id or self._new_run_id()
        memory = await self._load_memory_context(
            user_id=user_id,
            session_id=resolved_session_id,
            project_app_id=getattr(request, "project_app_id", None),
            external_user_id=getattr(request, "external_user_id", None),
        )
        return self.build_initial_state(
            request,
            user_id=user_id,
            session_id=resolved_session_id,
            chat_history=memory.messages,
            memory_summary=memory.summary,
        )

    async def _save_turn(
        self,
        *,
        state: dict[str, Any],
        answer: str,
        answer_status: str | None = None,
        log_id: int | None = None,
        retrieved_docs: list[dict[str, Any]] | None = None,
    ) -> None:
        session_id = state.get("session_id")
        user_id = state.get("user_id")
        if not session_id:
            return
        await self._memory_store.save_turn(
            user_id=int(user_id) if user_id else None,
            session_id=session_id,
            product_id=state.get("product_id"),
            project_id=state.get("project_id"),
            project_app_id=state.get("project_app_id"),
            external_user_id=state.get("external_user_id"),
            external_user_name=state.get("external_user_name"),
            team_id=state.get("team_id"),
            knowledge_base_id=state.get("knowledge_base_id"),
            assistant_id=state.get("assistant_id"),
            category_id=state.get("category_id"),
            user_message=state.get("query", ""),
            answer_message=answer,
            answer_metadata={
                "answer_status": answer_status,
                "log_id": log_id,
                "workflow_id": state.get("workflow_id") or (state.get("metadata") or {}).get("workflow"),
                "retrieval_execution_plan": (
                    dict(state.get("retrieval_execution_plan") or {})
                    if isinstance(state.get("retrieval_execution_plan"), dict)
                    else None
                ),
                "semantic_queries": list(state.get("semantic_queries") or []),
                "lexical_terms": list(state.get("lexical_terms") or []),
                "rewrite_trace": (
                    dict(state.get("rewrite_trace") or {})
                    if isinstance(state.get("rewrite_trace"), dict)
                    else None
                ),
                "retrieval_trace": (
                    dict(state.get("retrieval_trace") or {})
                    if isinstance(state.get("retrieval_trace"), dict)
                    else None
                ),
                "retrieval_evaluation": (
                    dict(state.get("retrieval_evaluation") or {})
                    if isinstance(state.get("retrieval_evaluation"), dict)
                    else None
                ),
                "candidate_entities": list(state.get("candidate_entities") or []),
                "answer_context": state.get("context"),
                "retrieved_docs": list(retrieved_docs or []),
                "page_context": (
                    dict(state.get("page_context") or {})
                    if isinstance(state.get("page_context"), dict)
                    else None
                ),
                "page_config": (
                    dict(state.get("page_config") or {})
                    if isinstance(state.get("page_config"), dict)
                    else None
                ),
            },
        )

    @staticmethod
    def _parse_stream_chunk(chunk: Any) -> tuple[str | None, dict[str, Any]]:
        """Normalize LangGraph stream chunks across supported wire shapes."""

        if isinstance(chunk, tuple) and len(chunk) == 2:
            mode, data = chunk
            if isinstance(mode, str) and isinstance(data, dict):
                return mode, data
            return None, {}

        if isinstance(chunk, dict):
            chunk_type = chunk.get("type")
            chunk_data = chunk.get("data", {})
            if isinstance(chunk_type, str) and isinstance(chunk_data, dict):
                return chunk_type, chunk_data

        return None, {}

    @staticmethod
    def _node_progress_message(node_id: str) -> str:
        if node_id == "analyze":
            return "正在理解问题..."
        if node_id == "rewrite_query":
            return "正在整理检索问题..."
        if node_id == "retrieve":
            return "正在检索知识库..."
        if node_id == "evaluate":
            return "Evaluating evidence..."
        if node_id == "answer":
            return "正在生成回答..."
        return "正在处理..."
    @staticmethod
    def _node_summary(node_id: str, state: dict[str, Any]) -> dict[str, Any]:
        if node_id == "analyze":
            return {
                "question_type": state.get("question_type"),
                "retrieval_required": state.get("retrieval_required"),
                "retrieval_complexity": state.get("retrieval_complexity"),
                "reason": state.get("route_reason"),
            }
        if node_id == "rewrite_query":
            rewrite_trace = state.get("rewrite_trace") or {}
            return {
                "rewrite_engine": rewrite_trace.get("engine"),
                "rewrite_policy": rewrite_trace.get("policy"),
                "semantic_query_count": rewrite_trace.get("semantic_query_count"),
                "lexical_term_count": rewrite_trace.get("lexical_term_count"),
                "fallback_used": rewrite_trace.get("fallback_used"),
            }
        if node_id == "retrieve":
            return {
                "retrieved_count": len(state.get("retrieved_docs", [])),
                "empty_reason": ((state.get("retrieval_trace") or {}).get("empty_reason")),
                "semantic_query_count": len(state.get("semantic_queries", []) or []),
                "lexical_term_count": len(state.get("lexical_terms", []) or []),
                "retrieval_mode": "vector_lexical_graph",
            }
        if node_id == "evaluate":
            evaluation = state.get("retrieval_evaluation") or {}
            return {
                "status": evaluation.get("status"),
                "next_action": evaluation.get("next_action"),
                "reason": evaluation.get("reason"),
            }
        if node_id == "answer":
            return {"answer_length": len(state.get("answer", ""))}
        return {"keys": sorted(state.keys())}

    @staticmethod
    def _resolve_answer_status(result: dict[str, Any]) -> str:
        if isinstance(result.get("answer_status"), str) and result.get("answer_status"):
            return str(result["answer_status"])
        if result.get("answer"):
            return "answered"
        return "partial"

    @staticmethod
    def _resolve_retrieval_status(*, retrieval_trace: dict[str, Any], retrieved_count: int) -> str | None:
        empty_reason = str(retrieval_trace.get("empty_reason") or "").strip()
        if empty_reason in {"empty_knowledge_base", "empty_collection"}:
            return empty_reason
        if retrieved_count > 0:
            return "ok"
        if empty_reason:
            return "no_hits"
        return None

    @staticmethod
    def _build_log_trace_payload(
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
            text_trace.get("funnel")
            if isinstance(text_trace.get("funnel"), dict)
            else {}
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
            return [
                str(item).strip()
                for item in list(value or [])
                if str(item or "").strip()
            ]

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
            if source in {"graph", "graph_summary", "graph_relation_summary"}:
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
            top_change_by_title = {
                str(item.get("title") or ""): item
                for item in list(rerank_trace.get("top_changes") or [])
                if isinstance(item, dict)
            }
            for index, doc in enumerate(raw_docs, start=1):
                if not isinstance(doc, dict):
                    continue
                metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
                title = str(metadata.get("document_title") or f"候选片段 #{index}")
                source_type = _source_type(metadata)
                top_change = top_change_by_title.get(title) or {}
                raw_original_rank = top_change.get("old_rank")
                try:
                    original_rank = int(raw_original_rank)
                except (TypeError, ValueError):
                    original_rank = index
                docs.append(
                    {
                        "rank": int(doc.get("rank") or index),
                        "original_rank": original_rank,
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

        final_context_docs = _build_trace_docs(list(result.get("primary_evidence_docs") or retrieved_docs or []))
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
            doc["selected"] = bool(doc.get("identity") and doc.get("identity") in selected_identities)

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
                    "candidate_count": int(retrieval_trace.get("graph_primary_count") or graph_hit_count),
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
            "supporting_evidence_docs": _build_trace_docs(list(result.get("supporting_evidence_docs") or [])),
            "metadata_evidence_docs": _build_trace_docs(list(result.get("metadata_evidence_docs") or [])),
            "debug": {
                "retrieval_trace": (
                    retrieval_trace
                ),
                "retrieval_evaluation": (
                    dict(result.get("retrieval_evaluation") or {})
                    if isinstance(result.get("retrieval_evaluation"), dict)
                    else {}
                ),
                "rewrite_trace": (
                    dict(result.get("rewrite_trace") or {})
                    if isinstance(result.get("rewrite_trace"), dict)
                    else {}
                ),
            },
        }

    @staticmethod
    def _log_retrieval_summary(
        *,
        state: dict[str, Any],
        result: dict[str, Any],
        total_latency_ms: int,
    ) -> None:
        retrieval_trace = dict(result.get("retrieval_trace") or {})
        text_trace = dict(retrieval_trace.get("text") or {})
        graph_trace = dict(retrieval_trace.get("graph") or {})
        rerank_trace = dict(retrieval_trace.get("rerank") or {})
        evaluation = dict(result.get("retrieval_evaluation") or {})
        rewrite_trace = dict(result.get("rewrite_trace") or {})
        plan_trace = dict(result.get("plan_trace") or {})
        evaluate_trace = dict(result.get("evaluate_trace") or {})
        answer_trace = dict(result.get("answer_trace") or {})
        semantic_queries = list(result.get("semantic_queries") or [])
        lexical_terms = list(result.get("lexical_terms") or [])
        candidate_entities = list(result.get("candidate_entities") or [])
        graph_used = graph_trace.get("graph_used")
        graph_hits = graph_trace.get("graph_hits", 0)
        graph_empty_reason = graph_trace.get("empty_reason")
        rerank_enabled = rerank_trace.get("rerank_enabled")
        rerank_changed = rerank_trace.get("top_docs_changed")
        top_changes = list(rerank_trace.get("top_changes") or [])
        top_changes_text = "\n".join(
            f"  - #{item.get('new_rank')}: 《{item.get('title') or 'Unknown document'}》 "
            f"(原 #{item.get('old_rank')} -> 新 #{item.get('new_rank')})"
            for item in top_changes[:3]
        ) or "  - (暂无)"

        logger.info(
            "\n[问答日志 {}] {}\n"
            "问题：{}\n"
            "会话：{}\n"
            "团队/知识库：{} / {}\n"
            "\n"
            "1. 问题理解\n"
            "- question_type: {}\n"
            "- retrieval_required: {}\n"
            "- retrieval_complexity: {}\n"
            "- reason: {}\n"
            "- latency_ms: {}\n"
            "\n"
            "2. 检索改写\n"
            "- 原问题: {}\n"
            "- 向量语义查询:\n{}\n"
            "- 关键词:\n{}\n"
            "- candidate_entities: {}\n"
            "- latency_ms: {}\n"
            "\n"
            "3. 文本检索\n"
            "- semantic_query_count: {}\n"
            "- lexical_term_count: {}\n"
            "- recall_k: {}\n"
            "- lexical_k: {}\n"
            "- 召回 chunk: {}\n"
            "- 去重后: {}\n"
            "- latency_ms: {}\n"
            "\n"
            "4. 图谱检索\n"
            "- graph_used: {}\n"
            "- matched_entities: {}\n"
            "- graph_hits: {}\n"
            "- empty_reason: {}\n"
            "- latency_ms: {}\n"
            "\n"
            "5. 重排\n"
            "- rerank_enabled: {}\n"
            "- 重排前候选: {}\n"
            "- 重排后保留: {}\n"
            "- rerank_top_docs_changed: {}\n"
            "- top_changes:\n{}\n"
            "- latency_ms: {}\n"
            "\n"
            "6. 结果合并\n"
            "- 文本证据: {}\n"
            "- 图谱补充证据: {}\n"
            "- final_context_docs: {}\n"
            "- empty_reason: {}\n"
            "- latency_ms: {}\n"
            "\n"
            "7. 证据评估\n"
            "- status: {}\n"
            "- next_action: {}\n"
            "- reason: {}\n"
            "- latency_ms: {}\n"
            "\n"
            "8. 最终回答\n"
            "- answer_status: {}\n"
            "- confidence: {}\n"
            "- latency_ms: {}\n"
            "- total_latency_ms: {}\n"
            "\n"
            "9. 审查信息\n"
            "- feedback: {}\n"
            "- suggested_review_label: {}\n"
            "- review_label: {}\n",
            result.get("log_id") or "-",
            result.get("created_at") or "-",
            str(result.get("query") or state.get("query") or ""),
            result.get("session_id") or state.get("session_id"),
            result.get("team_name") or result.get("team_id") or state.get("team_id") or "-",
            result.get("knowledge_base_name")
            or result.get("knowledge_base_id")
            or state.get("knowledge_base_id")
            or "-",
            result.get("question_type") or state.get("question_type"),
            result.get("retrieval_required") if result.get("retrieval_required") is not None else state.get("retrieval_required"),
            result.get("retrieval_complexity") or state.get("retrieval_complexity"),
            result.get("route_reason") or result.get("reason") or state.get("route_reason"),
            plan_trace.get("latency_ms", 0),
            str(result.get("query") or state.get("query") or ""),
            "\n".join(
                f"  {index + 1}) {query}" for index, query in enumerate(semantic_queries[:3])
            ) or "  (none)",
            ", ".join(str(term) for term in lexical_terms[:12]) or "(none)",
            ", ".join(candidate_entities) if candidate_entities else "(none)",
            rewrite_trace.get("latency_ms", 0),
            text_trace.get("semantic_query_count") or len(semantic_queries),
            text_trace.get("lexical_term_count") or len(lexical_terms),
            text_trace.get("recall_k", 0),
            text_trace.get("lexical_k", 0),
            text_trace.get("raw_candidate_count", 0),
            text_trace.get("merged_candidate_count", text_trace.get("raw_candidate_count", 0)),
            text_trace.get("latency_ms", 0),
            graph_used,
            ", ".join(candidate_entities) if candidate_entities else "(none)",
            graph_hits,
            graph_empty_reason or "(none)",
            graph_trace.get("latency_ms", 0),
            rerank_enabled,
            rerank_trace.get("candidate_count", 0),
            rerank_trace.get("final_count", 0),
            rerank_changed,
            top_changes_text,
            rerank_trace.get("latency_ms", 0),
            retrieval_trace.get("text_evidence_count", 0),
            retrieval_trace.get("graph_evidence_count", 0),
            retrieval_trace.get("final_context_docs", retrieval_trace.get("final_hits", 0)),
            retrieval_trace.get("empty_reason"),
            retrieval_trace.get("merge_latency_ms", 0),
            evaluation.get("status"),
            evaluation.get("next_action"),
            evaluation.get("reason"),
            evaluate_trace.get("latency_ms", 0),
            result.get("answer_status"),
            answer_trace.get("confidence") or "-",
            answer_trace.get("latency_ms", 0),
            total_latency_ms,
            result.get("feedback_value") or "(none)",
            result.get("suggested_review_label") or "(none)",
            result.get("review_label") or "（未审核）",
        )

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
        evaluation = dict(result.get("retrieval_evaluation") or {})
        rewrite_trace = dict(result.get("rewrite_trace") or {})
        route_trace = dict(result.get("route_trace") or {})
        plan_trace = dict(result.get("plan_trace") or {})
        evaluate_trace = dict(result.get("evaluate_trace") or {})
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
            return "\n".join(
                f"  {index + 1}. {value}" for index, value in enumerate(values[:3])
            )

        def _format_top_changes(items: list[dict[str, Any]]) -> str:
            if not items:
                return "  - (none)"
            return "\n".join(
                f"  - #{item.get('new_rank')}: 《{item.get('title') or 'Unknown document'}》 "
                f"(原 #{item.get('old_rank')} -> 新 #{item.get('new_rank')})"
                for item in items[:3]
            )

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
            "- rerank_enabled: {}\n"
            "- rerank_top_docs_changed: {}\n"
            "- top_changes:\n{}\n"
            "- empty_reason: {}\n"
            "- retrieval_latency_ms: {}\n"
            "- merge_latency_ms: {}\n"
            "\n"
            "4. 证据评估\n"
            "- status: {}\n"
            "- next_action: {}\n"
            "- reason: {}\n"
            "- evaluate_latency_ms: {}\n"
            "\n"
            "5. 答案生成\n"
            "- answer_status: {}\n"
            "- confidence: {}\n"
            "- answer_latency_ms: {}\n"
            "- total_latency_ms: {}\n"
            "\n"
            "6. 审查信息\n"
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
            result.get("retrieval_required")
            if result.get("retrieval_required") is not None
            else state.get("retrieval_required"),
            result.get("retrieval_complexity") or state.get("retrieval_complexity") or "-",
            result.get("route_reason")
            or result.get("reason")
            or state.get("route_reason")
            or "-",
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
                retrieval_trace.get("final_context_docs")
                or retrieval_trace.get("final_hits")
                or 0
            ),
            bool(rerank_trace.get("rerank_enabled")),
            bool(rerank_trace.get("top_docs_changed")),
            _format_top_changes(list(rerank_trace.get("top_changes") or [])),
            retrieval_trace.get("empty_reason") or graph_trace.get("empty_reason") or "-",
            int(text_trace.get("latency_ms") or retrieval_trace.get("text_retrieval_latency_ms") or 0),
            int(retrieval_trace.get("merge_latency_ms") or 0),
            evaluation.get("status") or "-",
            evaluation.get("next_action") or "-",
            evaluation.get("reason") or "-",
            int(evaluate_trace.get("latency_ms") or 0),
            result.get("answer_status") or "-",
            answer_trace.get("confidence") or "-",
            int(answer_trace.get("latency_ms") or 0),
            total_latency_ms,
            result.get("feedback_value") or "(none)",
            result.get("suggested_review_label") or "(none)",
            result.get("review_label") or "（未审核）",
        )

    @staticmethod
    def _log_retrieval_review_log(
        *,
        state: dict[str, Any],
        result: dict[str, Any],
        total_latency_ms: int,
    ) -> None:
        message = KbChatService._build_retrieval_review_log_message(
            state=state,
            result=result,
            total_latency_ms=total_latency_ms,
        )
        if message:
            logger.bind(kb_review_log=True).info(message)

    async def _record_log(
        self,
        *,
        state: dict[str, Any],
        result: dict[str, Any],
        latency_ms: int | None,
    ) -> int | None:
        user_id = state.get("user_id")
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
        retrieved_docs = list(result.get("retrieved_docs") or [])
        trace_payload = self._build_log_trace_payload(
            state=state,
            result=result,
            retrieved_docs=retrieved_docs,
        )
        retrieval_status = self._resolve_retrieval_status(
            retrieval_trace=retrieval_trace,
            retrieved_count=len(retrieved_docs),
        )
        try:
            async with AsyncSessionLocal() as db:
                repo = KbChatLogRepository(db)
                row = await repo.create_log(
                    user_id=int(user_id) if user_id else None,
                    session_id=state.get("session_id"),
                    product_id=state.get("product_id"),
                    project_id=state.get("project_id"),
                    project_app_id=state.get("project_app_id"),
                    external_user_id=state.get("external_user_id"),
                    external_user_name=state.get("external_user_name"),
                    knowledge_base_id=state.get("knowledge_base_id"),
                    assistant_id=state.get("assistant_id"),
                    category_id=state.get("category_id"),
                    query=str(state.get("query") or ""),
                    answer_text=str(result.get("answer") or ""),
                    answer_status=self._resolve_answer_status(result),
                    retrieval_status=retrieval_status,
                    latency_ms=latency_ms,
                    text_hit_count=int(text_trace.get("text_hits") or 0),
                    graph_hit_count=int(graph_trace.get("graph_hits") or 0),
                    merged_candidate_count=int(
                        retrieval_trace.get("merged_pool_count")
                        or text_trace.get("merged_candidate_count")
                        or 0
                    ),
                    final_context_count=int(retrieval_trace.get("final_context_docs") or len(retrieved_docs)),
                    empty_reason=str(retrieval_trace.get("empty_reason") or "") or None,
                    rerank_enabled=bool(rerank_trace.get("enabled_for_primary_evidence")),
                    trace_payload=trace_payload,
                )
                return row.id
        except Exception as exc:
            logger.exception("[KB Chat] failed to persist log: {}", exc)
            return None

    async def _record_content_risk_log(
        self,
        *,
        state: dict[str, Any],
        check_result: ContentRiskDetectionResult,
        checked_text: str,
        chat_log_id: int | None,
    ) -> int | None:
        if not check_result.hits:
            return None

        user_id = state.get("user_id")
        hits = [
            {
                "rule_id": hit.rule_id,
                "library_id": hit.library_id,
                "rule_name": hit.rule_name,
                "risk_category": hit.risk_category,
                "risk_level": hit.risk_level,
                "action": hit.action,
                "match_mode": hit.match_mode,
                "pattern": hit.pattern,
                "matched_text": hit.matched_text,
            }
            for hit in check_result.hits
        ]
        matched_text = "、".join(
            dict.fromkeys(hit.matched_text for hit in check_result.hits if hit.matched_text)
        )

        try:
            async with AsyncSessionLocal() as db:
                row = await ContentRiskLogRepository(db).create_log(
                    ContentRiskLog(
                        chat_log_id=chat_log_id,
                        user_id=int(user_id) if user_id else None,
                        session_id=state.get("session_id"),
                        team_id=state.get("team_id"),
                        product_id=state.get("product_id"),
                        project_id=state.get("project_id"),
                        project_app_id=state.get("project_app_id"),
                        external_user_id=state.get("external_user_id"),
                        external_user_name=state.get("external_user_name"),
                        knowledge_base_id=state.get("knowledge_base_id"),
                        assistant_id=state.get("assistant_id"),
                        scene=check_result.scene,
                        action=check_result.action,
                        blocked=check_result.blocked,
                        risk_level=check_result.risk_level,
                        matched_text=matched_text or None,
                        checked_text=checked_text,
                        hits=hits,
                        elapsed_ms=check_result.elapsed_ms,
                    )
                )
                return row.id
        except Exception as exc:
            logger.exception("[KB Chat] failed to persist content-risk log: {}", exc)
            return None

    @staticmethod
    def _build_blocked_result(
        state: dict[str, Any],
        check_result: ContentRiskDetectionResult,
    ) -> dict[str, Any]:
        matched_names = [hit.rule_name for hit in check_result.hits]
        matched = "、".join(matched_names[:5])
        suffix = "等规则" if len(matched_names) > 5 else "规则"
        answer = (
            f"内容命中{matched}{suffix}，当前请求已被内容风控拦截。"
            if matched
            else "内容命中风控规则，当前请求已被拦截。"
        )
        return {
            **state,
            "answer": answer,
            "retrieved_docs": [],
            "retrieval_execution_plan": {},
            "semantic_queries": [],
            "lexical_terms": [],
            "context": "",
            "content_risk_action": check_result.action,
            "content_risk_scene": check_result.scene,
            "content_risk_hits": [
                {
                    "rule_id": hit.rule_id,
                    "library_id": hit.library_id,
                    "rule_name": hit.rule_name,
                    "risk_category": hit.risk_category,
                    "risk_level": hit.risk_level,
                    "action": hit.action,
                    "matched_text": hit.matched_text,
                }
                for hit in check_result.hits
            ],
            "answer_status": "blocked",
        }

    async def _check_content_risk(
        self,
        *,
        scene: str,
        text: str,
    ) -> ContentRiskDetectionResult:
        return await self._content_risk_detection_service.check_text(
            scene=scene,
            text=text,
        )

    async def invoke(self, request: "KbChatRequest", *, user_id: int | None) -> "KbChatResponse":
        """Run the chat graph and map its result to the response schema."""

        from app.models.schemas.kb_chat import KbChatResponse

        state = await self._prepare_state(request, user_id=user_id)
        query_risk_check = await self._check_content_risk(scene="query", text=request.query)
        if query_risk_check.blocked:
            result = self._build_blocked_result(state, query_risk_check)
            answer_status = self._resolve_answer_status(result)
            log_id = await self._record_log(
                state=state,
                result=result,
                latency_ms=0,
            )
            await self._record_content_risk_log(
                state=state,
                check_result=query_risk_check,
                checked_text=request.query,
                chat_log_id=log_id,
            )
            await self._save_turn(
                state=result,
                answer=result["answer"],
                answer_status=answer_status,
                log_id=log_id,
                retrieved_docs=[],
            )
            return KbChatResponse(
                answer=result["answer"],
                answer_text=result["answer"],
                answer_status=answer_status,
                backend_citations=[],
                retrieved_docs=[],
                assistant_id=state.get("assistant_id"),
                assistant_name=state.get("assistant_name"),
                session_id=state.get("session_id"),
                log_id=log_id,
            )

        started_at = perf_counter()
        result = await self._get_graph().ainvoke(state)
        answer = result.get("answer", "")
        answer_risk_check = await self._check_content_risk(scene="answer", text=answer)
        blocked_answer_text = answer
        if answer_risk_check.blocked:
            result = self._build_blocked_result({**state, **result}, answer_risk_check)
            answer = result.get("answer", "")
        answer_status = self._resolve_answer_status(result)
        total_latency_ms = int((perf_counter() - started_at) * 1000)
        self._log_retrieval_review_log(
            state=state,
            result=result,
            total_latency_ms=total_latency_ms,
        )
        log_id = await self._record_log(
            state=state,
            result=result,
            latency_ms=total_latency_ms,
        )
        await self._record_content_risk_log(
            state=state,
            check_result=answer_risk_check,
            checked_text=blocked_answer_text,
            chat_log_id=log_id,
        )
        await self._save_turn(
            state=result,
            answer=answer,
            answer_status=answer_status,
            log_id=log_id,
            retrieved_docs=list(result.get("retrieved_docs", []) or []),
        )
        return KbChatResponse(
            answer=answer,
            answer_text=answer,
            answer_status=answer_status,
            backend_citations=result.get("retrieved_docs", []),
            retrieved_docs=result.get("retrieved_docs", []),
            assistant_id=state.get("assistant_id"),
            assistant_name=state.get("assistant_name"),
            session_id=state.get("session_id"),
            log_id=log_id,
        )

    async def preview(self, request: "KbChatRequest", *, user_id: int | None) -> "KbChatResponse":
        """Run a stateless preview without persisting chat memory or logs."""

        from app.models.schemas.kb_chat import KbChatResponse

        state = self.build_initial_state(
            request,
            user_id=user_id,
            session_id=self._new_run_id(),
            chat_history=[],
            memory_summary=None,
        )
        query_risk_check = await self._check_content_risk(scene="query", text=request.query)
        if query_risk_check.blocked:
            result = self._build_blocked_result(state, query_risk_check)
            answer_status = self._resolve_answer_status(result)
            return KbChatResponse(
                answer=result["answer"],
                answer_text=result["answer"],
                answer_status=answer_status,
                backend_citations=[],
                retrieved_docs=[],
                assistant_id=state.get("assistant_id"),
                assistant_name=state.get("assistant_name"),
                session_id=None,
                log_id=None,
            )

        result = await self._get_graph().ainvoke(state)
        answer_risk_check = await self._check_content_risk(
            scene="answer",
            text=str(result.get("answer") or ""),
        )
        if answer_risk_check.blocked:
            result = self._build_blocked_result({**state, **result}, answer_risk_check)
        answer_status = self._resolve_answer_status(result)
        return KbChatResponse(
            answer=result.get("answer", ""),
            answer_text=result.get("answer", ""),
            answer_status=answer_status,
            backend_citations=result.get("retrieved_docs", []),
            retrieved_docs=result.get("retrieved_docs", []),
            assistant_id=state.get("assistant_id"),
            assistant_name=state.get("assistant_name"),
            session_id=None,
            log_id=None,
        )

    async def list_sessions(
        self,
        *,
        user_id: int | None,
        limit: int = 30,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> list["KbChatSessionSummary"]:
        """List persisted KB chat sessions for the current user."""

        from app.models.schemas.kb_chat import KbChatSessionSummary

        records = await self._memory_store.list_sessions(
            user_id=user_id,
            limit=limit,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
        )
        return [
            KbChatSessionSummary(
                session_id=record.session_id,
                title=record.title,
                preview=record.preview,
                product_id=record.product_id,
                project_id=record.project_id,
                project_app_id=record.project_app_id,
                external_user_id=record.external_user_id,
                external_user_name=record.external_user_name,
                team_id=record.team_id,
                knowledge_base_id=record.knowledge_base_id,
                knowledge_base_name=record.knowledge_base_name,
                assistant_id=record.assistant_id,
                assistant_name=record.assistant_name,
                category_id=record.category_id,
                category_name=record.category_name,
                message_count=record.message_count,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
            for record in records
        ]

    async def get_session(
        self,
        *,
        user_id: int | None,
        session_id: str,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> "KbChatSessionDetail | None":
        """Load one persisted KB chat session for the current user."""

        from app.models.schemas.kb_chat import KbChatSessionDetail, KbChatSessionMessage

        record = await self._memory_store.get_session_detail(
            user_id=user_id,
            session_id=session_id,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
        )
        if record is None:
            return None

        return KbChatSessionDetail(
            session_id=record.session_id,
            title=record.title,
            preview=record.preview,
            product_id=record.product_id,
            project_id=record.project_id,
            project_app_id=record.project_app_id,
            external_user_id=record.external_user_id,
            external_user_name=record.external_user_name,
            team_id=record.team_id,
            knowledge_base_id=record.knowledge_base_id,
            knowledge_base_name=record.knowledge_base_name,
            assistant_id=record.assistant_id,
            assistant_name=record.assistant_name,
            category_id=record.category_id,
            category_name=record.category_name,
            message_count=record.message_count,
            created_at=record.created_at,
            updated_at=record.updated_at,
            messages=[
                KbChatSessionMessage(
                    role=str(message.get("role") or ""),
                    content=str(message.get("content") or ""),
                    retrieved_docs=list(
                        ((message.get("metadata") or {}).get("retrieved_docs") or [])
                    ),
                    answer_status=(
                        (message.get("metadata") or {}).get("answer_status")
                        if isinstance((message.get("metadata") or {}).get("answer_status"), str)
                        else None
                    ),
                    log_id=(
                        (message.get("metadata") or {}).get("log_id")
                        if isinstance((message.get("metadata") or {}).get("log_id"), int)
                        else None
                    ),
                    created_at=message["created_at"],
                )
                for message in record.messages
            ],
        )

    async def delete_session(
        self,
        *,
        user_id: int | None,
        session_id: str,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> bool:
        """Delete one persisted KB chat session for the current user."""

        return await self._memory_store.delete_session(
            user_id=user_id,
            session_id=session_id,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
        )

    async def stream(
        self,
        request: "KbChatRequest",
        *,
        user_id: int | None,
    ) -> AsyncGenerator[str, None]:
        """Stream graph updates and answer tokens as standardized SSE messages."""

        state = await self._prepare_state(request, user_id=user_id)
        run_id = state.get("run_id")
        workflow_id = str(state.get("workflow_id") or self._workflow_id)
        graph = self._get_graph()
        started_nodes: set[str] = set()
        final_state = dict(state)
        started_at = perf_counter()

        try:
            yield emit_start(run_id, "开始知识库问答")
            query_risk_check = await self._check_content_risk(scene="query", text=request.query)
            if query_risk_check.blocked:
                blocked_state = self._build_blocked_result(state, query_risk_check)
                answer_status = self._resolve_answer_status(blocked_state)
                log_id = await self._record_log(
                    state=state,
                    result=blocked_state,
                    latency_ms=0,
                )
                await self._record_content_risk_log(
                    state=state,
                    check_result=query_risk_check,
                    checked_text=request.query,
                    chat_log_id=log_id,
                )
                await self._save_turn(
                    state=blocked_state,
                    answer=blocked_state["answer"],
                    answer_status=answer_status,
                    log_id=log_id,
                    retrieved_docs=[],
                )
                yield emit_complete(
                    run_id,
                    {
                        "answer": blocked_state["answer"],
                        "answer_text": blocked_state["answer"],
                        "answer_status": answer_status,
                        "backend_citations": [],
                        "retrieved_docs": [],
                        "assistant_id": state.get("assistant_id"),
                        "assistant_name": state.get("assistant_name"),
                        "session_id": state.get("session_id"),
                        "log_id": log_id,
                    },
                )
                return

            async for chunk in graph.astream(
                state,
                stream_mode=["updates", "custom"],
                version="v2",
            ):
                chunk_type, chunk_data = self._parse_stream_chunk(chunk)

                if chunk_type == "updates":
                    for node_id, node_state in chunk_data.items():
                        node_name = get_node_label(workflow_id, node_id)
                        if node_id not in started_nodes:
                            yield emit_node_start(
                                node_id,
                                node_name,
                                run_id,
                                message=self._node_progress_message(node_id),
                            )
                            started_nodes.add(node_id)

                        final_state.update(node_state)
                        if node_id == "retrieve":
                            yield emit_event(
                                AgentEventType.RETRIEVED,
                                {"retrieved_docs": node_state.get("retrieved_docs", [])},
                                node_id=node_id,
                                node_name=node_name,
                                run_id=run_id,
                            )

                        yield emit_node_complete(
                            node_id,
                            node_name,
                            run_id,
                            self._node_summary(node_id, node_state),
                        )
                elif chunk_type == "custom":
                    node_id = chunk_data.get("node_id") or "answer"
                    node_name = get_node_label(workflow_id, node_id)
                    if chunk_data.get("type") == "progress":
                        message = str(
                            chunk_data.get("message") or self._node_progress_message(node_id)
                        )
                        if node_id not in started_nodes:
                            yield emit_node_start(
                                node_id,
                                node_name,
                                run_id,
                                message=message,
                            )
                            started_nodes.add(node_id)
                        yield emit_progress(
                            run_id,
                            node_id=node_id,
                            node_name=node_name,
                            message=message,
                            data={
                                key: value
                                for key, value in chunk_data.items()
                                if key not in {"type", "node_id", "message"}
                            },
                        )
                        continue

                    if node_id not in started_nodes:
                        yield emit_node_start(
                            node_id,
                            node_name,
                            run_id,
                            message=self._node_progress_message(node_id),
                        )
                        started_nodes.add(node_id)

                    text = chunk_data.get("text")
                    if text:
                        yield emit_event(
                            AgentEventType.TOKEN,
                            {"text": text},
                            node_id=node_id,
                            node_name=node_name,
                            run_id=run_id,
                        )

            answer = final_state.get("answer", "")
            answer_risk_check = await self._check_content_risk(scene="answer", text=answer)
            blocked_answer_text = answer
            if answer_risk_check.blocked:
                final_state = self._build_blocked_result(final_state, answer_risk_check)
                answer = final_state.get("answer", "")
            answer_status = self._resolve_answer_status(final_state)
            total_latency_ms = int((perf_counter() - started_at) * 1000)
            self._log_retrieval_review_log(
                state=state,
                result=final_state,
                total_latency_ms=total_latency_ms,
            )
            log_id = await self._record_log(
                state=state,
                result=final_state,
                latency_ms=total_latency_ms,
            )
            await self._record_content_risk_log(
                state=state,
                check_result=answer_risk_check,
                checked_text=blocked_answer_text,
                chat_log_id=log_id,
            )
            await self._save_turn(
                state=final_state,
                answer=answer,
                answer_status=answer_status,
                log_id=log_id,
                retrieved_docs=list(final_state.get("retrieved_docs", []) or []),
            )
            yield emit_complete(
                run_id,
                {
                    "answer": answer,
                    "answer_text": answer,
                    "answer_status": answer_status,
                    "backend_citations": final_state.get("retrieved_docs", []),
                    "retrieved_docs": final_state.get("retrieved_docs", []),
                    "assistant_id": state.get("assistant_id"),
                    "assistant_name": state.get("assistant_name"),
                    "session_id": state.get("session_id"),
                    "log_id": log_id,
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("[KB Chat] stream failed after retrieval/answer stage: {}", exc)
            yield emit_error(run_id, str(exc))


kb_chat_service: KbChatService | None = None


def get_kb_chat_service() -> KbChatService:
    global kb_chat_service
    if kb_chat_service is None:
        kb_chat_service = KbChatService()
    return kb_chat_service
