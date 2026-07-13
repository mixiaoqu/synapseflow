"""Application service for end-user knowledge-base chat."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, cast

from fastapi import HTTPException
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
    emit_workflow_complete,
)
from app.application.workflow_meta import (
    OUTPUT_NODE_IDS,
    build_node_summary,
    get_node_label,
    get_node_progress_message,
    normalize_activity_payload,
)
from app.db.models import ContentRiskLog
from app.db.session import AsyncSessionLocal
from app.repositories.content_risk_log_repository import ContentRiskLogRepository
from app.repositories.kb_chat_log_repository import KbChatLogRepository
from app.services.chat_memory import (
    ChatMemoryContext,
    ChatMemoryStore,
    DatabaseChatMemoryStore,
)
from app.services.chat_memory_summary import (
    ChatMemorySummaryService,
    ChatMemorySummaryStore,
)
from app.services.content_risk_detection_service import (
    ContentRiskDetectionResult,
    get_content_risk_detection_service,
)
from app.services.document_lifecycle import VISIBLE_ASK_DOCUMENT_STATUSES

if TYPE_CHECKING:
    from app.models.schemas.kb_chat import (
        KbChatRequest,
        KbChatResponse,
        KbChatSessionDetail,
        KbChatSessionSummary,
    )


class KbChatService(BaseAgentService):
    """Encapsulates end-user knowledge-base chat orchestration."""

    _PUBLIC_STREAM_ERROR_MESSAGE = "抱歉，当前服务暂时不可用，请稍后重试。"

    def __init__(
        self,
        llm_factory: Callable[[], Any] | None = None,
        graph: Any | None = None,
        memory_store: ChatMemoryStore | None = None,
        memory_summary_service: ChatMemorySummaryService | None = None,
        content_risk_detection_service: Any | None = None,
    ):
        self._llm_factory = llm_factory
        self._graph = graph
        self._workflow_id = "agent"
        self._memory_store = memory_store or DatabaseChatMemoryStore()
        self._memory_summary_service = memory_summary_service
        if self._memory_summary_service is None and isinstance(
            self._memory_store, DatabaseChatMemoryStore
        ):
            self._memory_summary_service = ChatMemorySummaryService()
        self._content_risk_detection_service = (
            content_risk_detection_service or get_content_risk_detection_service()
        )

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
                "store_id": getattr(request, "store_id", None),
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
                "allowed_document_statuses": list(
                    getattr(request, "allowed_document_statuses", None)
                    or VISIBLE_ASK_DOCUMENT_STATUSES
                ),
                "normalized_query": "",
                "scope": {},
                "session_context": {},
                "channel_context": {},
                "trace": {},
                "classification": {},
                "route": {},
                "task_plan": {},
                "execution_runs": {},
                "collected_results": {},
                "synthesized_result": {},
                "retrieved_docs": [],
                "answer": "",
                "workflow_result": {},
                "answer_status": "",
            },
        )
        return state

    def _get_graph(self) -> Any:
        if self._graph is None:
            from app.agents.graphs.agent_graph import create_agent_graph

            self._graph = create_agent_graph(llm_factory=self._llm_factory)
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
                "workflow_id": state.get("workflow_id")
                or (state.get("metadata") or {}).get("workflow"),
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
                "candidate_entities": list(state.get("candidate_entities") or []),
                "answer_context": state.get("context"),
                "retrieved_docs": list(retrieved_docs or []),
                "page_context": (
                    dict(state.get("page_context") or {})
                    if isinstance(state.get("page_context"), dict)
                    else None
                ),
                "store_id": state.get("store_id"),
                "page_config": (
                    dict(state.get("page_config") or {})
                    if isinstance(state.get("page_config"), dict)
                    else None
                ),
            },
        )
        if self._memory_summary_service is not None:
            try:
                await self._memory_summary_service.refresh(
                    cast(ChatMemorySummaryStore, self._memory_store),
                    user_id=int(user_id) if user_id else None,
                    session_id=session_id,
                    project_app_id=state.get("project_app_id"),
                    external_user_id=state.get("external_user_id"),
                )
            except Exception as exc:
                logger.exception(
                    "[Chat Memory] failed to refresh session summary | session_id={} error={}",
                    session_id,
                    exc,
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
    def _retrieved_docs_from_node_state(node_state: dict[str, Any]) -> list[dict[str, Any]]:
        retrieval_result = dict(node_state.get("retrieval_result") or {})
        return [
            {
                "content": item.get("content") or "",
                "metadata": {
                    **dict(item.get("source") or {}),
                    "ref_id": item.get("ref_id"),
                    "role": item.get("role"),
                    "kind": item.get("kind"),
                },
            }
            for item in list(retrieval_result.get("evidence_items") or [])
            if isinstance(item, dict) and item.get("role") == "primary"
        ]

    @staticmethod
    def _resolve_answer_status(result: dict[str, Any]) -> str:
        if isinstance(result.get("answer_status"), str) and result.get("answer_status"):
            return str(result["answer_status"])
        if result.get("answer"):
            return "answered"
        return "partial"

    @staticmethod
    def _resolve_retrieval_status(
        *, retrieval_trace: dict[str, Any], retrieved_count: int
    ) -> str | None:
        empty_reason = str(retrieval_trace.get("empty_reason") or "").strip()
        if empty_reason in {"empty_knowledge_base", "empty_collection"}:
            return empty_reason
        if retrieved_count > 0:
            return "ok"
        if empty_reason:
            return "no_hits"
        return None

    @classmethod
    def _public_stream_error_message(cls, exc: Exception) -> str:
        if isinstance(exc, HTTPException):
            detail = exc.detail
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
        return cls._PUBLIC_STREAM_ERROR_MESSAGE

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
                    final_context_count=int(
                        retrieval_trace.get("final_context_docs") or len(retrieved_docs)
                    ),
                    empty_reason=str(retrieval_trace.get("empty_reason") or "") or None,
                    rerank_enabled=bool(rerank_trace.get("enabled")),
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
        started_nodes: set[tuple[str, str]] = set()
        workflow_completed_for_answer = False
        final_state = dict(state)
        started_at = perf_counter()

        try:
            yield emit_start(run_id, "开始处理请求", workflow_id=workflow_id)
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
                    workflow_id=workflow_id,
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
                        node_workflow_id = workflow_id
                        node_key = (node_workflow_id, node_id)
                        node_name = get_node_label(node_workflow_id, node_id)
                        if node_key not in started_nodes:
                            yield emit_node_start(
                                node_id,
                                node_name,
                                run_id,
                                workflow_id=node_workflow_id,
                                message=get_node_progress_message(node_workflow_id, node_id),
                            )
                            started_nodes.add(node_key)

                        final_state.update(node_state)
                        if node_id == "retrieve_knowledge":
                            yield emit_event(
                                AgentEventType.RETRIEVED,
                                {
                                    "retrieved_docs": self._retrieved_docs_from_node_state(
                                        node_state
                                    )
                                },
                                workflow_id=node_workflow_id,
                                node_id=node_id,
                                node_name=node_name,
                                run_id=run_id,
                            )

                        yield emit_node_complete(
                            node_id,
                            node_name,
                            run_id,
                            build_node_summary(node_workflow_id, node_id, node_state),
                            workflow_id=node_workflow_id,
                        )
                elif chunk_type == "custom":
                    node_id = str(chunk_data.get("node_id") or "").strip()
                    if not node_id:
                        raise ValueError("Custom stream event is missing node_id")
                    node_workflow_id = str(chunk_data.get("workflow_id") or "").strip()
                    if not node_workflow_id:
                        raise ValueError(
                            f"Custom stream event is missing workflow_id: node_id={node_id}"
                        )
                    node_key = (node_workflow_id, node_id)
                    node_name = get_node_label(node_workflow_id, node_id)
                    if chunk_data.get("type") == "node_complete":
                        node_state = (
                            chunk_data.get("node_state")
                            if isinstance(chunk_data.get("node_state"), dict)
                            else {}
                        )
                        if node_key not in started_nodes:
                            yield emit_node_start(
                                node_id,
                                node_name,
                                run_id,
                                workflow_id=node_workflow_id,
                                message=get_node_progress_message(node_workflow_id, node_id),
                            )
                            started_nodes.add(node_key)

                        if node_id == "retrieve_knowledge":
                            yield emit_event(
                                AgentEventType.RETRIEVED,
                                {
                                    "retrieved_docs": self._retrieved_docs_from_node_state(
                                        node_state
                                    )
                                },
                                workflow_id=node_workflow_id,
                                node_id=node_id,
                                node_name=node_name,
                                run_id=run_id,
                            )

                        yield emit_node_complete(
                            node_id,
                            node_name,
                            run_id,
                            build_node_summary(node_workflow_id, node_id, node_state),
                            workflow_id=node_workflow_id,
                        )
                        continue

                    if chunk_data.get("type") == "progress":
                        message = str(
                            chunk_data.get("message")
                            or get_node_progress_message(node_workflow_id, node_id)
                        )
                        if node_key not in started_nodes:
                            yield emit_node_start(
                                node_id,
                                node_name,
                                run_id,
                                workflow_id=node_workflow_id,
                                message=message,
                            )
                            started_nodes.add(node_key)
                        yield emit_progress(
                            run_id,
                            workflow_id=node_workflow_id,
                            node_id=node_id,
                            node_name=node_name,
                            message=message,
                            data=normalize_activity_payload(
                                workflow_id=node_workflow_id,
                                node_id=node_id,
                                node_name=node_name,
                                payload={
                                    key: value
                                    for key, value in chunk_data.items()
                                    if key not in {"type", "workflow_id", "node_id", "message"}
                                },
                            ),
                        )
                        continue

                    if node_key not in started_nodes:
                        yield emit_node_start(
                            node_id,
                            node_name,
                            run_id,
                            workflow_id=node_workflow_id,
                            message=get_node_progress_message(node_workflow_id, node_id),
                        )
                        started_nodes.add(node_key)

                    text = chunk_data.get("text")
                    if text:
                        if node_id in OUTPUT_NODE_IDS and not workflow_completed_for_answer:
                            yield emit_workflow_complete(run_id, workflow_id=workflow_id)
                            workflow_completed_for_answer = True
                        yield emit_event(
                            AgentEventType.TOKEN,
                            {"text": text},
                            workflow_id=node_workflow_id,
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
                workflow_id=workflow_id,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("[KB Chat] stream failed after retrieval/answer stage: {}", exc)
            yield emit_error(
                run_id, self._public_stream_error_message(exc), workflow_id=workflow_id
            )


kb_chat_service: KbChatService | None = None


def get_kb_chat_service() -> KbChatService:
    global kb_chat_service
    if kb_chat_service is None:
        kb_chat_service = KbChatService()
    return kb_chat_service
