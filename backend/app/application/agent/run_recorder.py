"""Persistence boundary for completed Agent turns."""

from __future__ import annotations

from typing import Any, cast

from loguru import logger

from app.db.models import ContentRiskLog
from app.db.session import AsyncSessionLocal
from app.repositories.content_risk_log_repository import ContentRiskLogRepository
from app.repositories.kb_chat_log_repository import KbChatLogRepository
from app.services.chat_memory import ChatMemoryStore
from app.services.chat_memory_summary import (
    ChatMemorySummaryService,
    ChatMemorySummaryStore,
)
from app.services.content_risk_detection_service import ContentRiskDetectionResult


class AgentRunRecorder:
    """Persist a completed turn and refresh its derived conversation summary."""

    def __init__(
        self,
        *,
        memory_store: ChatMemoryStore,
        memory_summary_service: ChatMemorySummaryService | None,
    ):
        self._memory_store = memory_store
        self._memory_summary_service = memory_summary_service

    async def save_turn(
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
        if self._memory_summary_service is None:
            return
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

    async def record_chat_log(
        self,
        *,
        state: dict[str, Any],
        result: dict[str, Any],
        latency_ms: int | None,
        trace_payload: dict[str, Any],
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
        retrieved_docs = [
            doc for doc in list(result.get("retrieved_docs") or [])
            if (doc.get("metadata") or {}).get("source_type") != "web"
        ]
        empty_reason = str(retrieval_trace.get("empty_reason") or "").strip()
        if empty_reason in {"empty_knowledge_base", "empty_collection"}:
            retrieval_status = empty_reason
        elif retrieved_docs:
            retrieval_status = "ok"
        elif empty_reason:
            retrieval_status = "no_hits"
        else:
            retrieval_status = None
        answer_status = str(result.get("answer_status") or "").strip()
        if not answer_status:
            answer_status = "answered" if result.get("answer") else "partial"

        try:
            async with AsyncSessionLocal() as db:
                row = await KbChatLogRepository(db).create_log(
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
                    answer_status=answer_status,
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
                    empty_reason=empty_reason or None,
                    rerank_enabled=bool(rerank_trace.get("enabled")),
                    input_tokens=result.get("input_tokens"),
                    output_tokens=result.get("output_tokens"),
                    total_tokens=result.get("total_tokens"),
                    estimated_cost=result.get("estimated_cost"),
                    token_usage=result.get("token_usage"),
                    trace_payload=trace_payload,
                )
                return row.id
        except Exception as exc:
            logger.exception("[Agent Run] failed to persist chat log: {}", exc)
            return None

    @staticmethod
    async def record_content_risk_log(
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
            logger.exception("[Agent Run] failed to persist content-risk log: {}", exc)
            return None
