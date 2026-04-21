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
    emit_start,
)
from app.application.workflow_meta import get_node_label
from app.db.session import AsyncSessionLocal
from app.repositories.kb_chat_log_repository import KbChatLogRepository
from app.services.document_lifecycle import RETRIEVAL_VERSION_LIVE, VISIBLE_ASK_DOCUMENT_STATUSES
from app.services.chat_memory import (
    ChatMemoryContext,
    ChatMemoryStore,
    DatabaseChatMemoryStore,
)
from app.services.sensitive_word_service import SensitiveWordCheckResult, get_sensitive_word_service

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
        sensitive_word_service: Any | None = None,
    ):
        self._llm_factory = llm_factory
        self._graph = graph
        self._memory_store = memory_store or DatabaseChatMemoryStore()
        self._sensitive_word_service = sensitive_word_service or get_sensitive_word_service()

    def build_initial_state(
        self,
        request: "KbChatRequest",
        *,
        user_id: int,
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
            metadata={"workflow": "kb_chat"},
        )
        return self.build_state(
            context,
            {
                "session_id": resolved_session_id,
                "query": request.query,
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
                "chat_history": history,
                "memory_summary": memory_summary,
                "retrieval_queries": [],
                "allowed_document_statuses": list(
                    getattr(request, "allowed_document_statuses", None)
                    or VISIBLE_ASK_DOCUMENT_STATUSES
                ),
                "retrieval_version_mode": (
                    getattr(request, "retrieval_version_mode", None)
                    or RETRIEVAL_VERSION_LIVE
                ),
                "retrieved_docs": [],
                "context": "",
                "answer": "",
                "kb_retrieval_status": None,
            },
        )

    def _get_graph(self) -> Any:
        if self._graph is None:
            from app.agents.graphs.kb_chat_graph import create_kb_chat_graph

            self._graph = create_kb_chat_graph(llm_factory=self._llm_factory)
        return self._graph

    async def _load_memory_context(
        self,
        *,
        user_id: int,
        session_id: str,
    ) -> ChatMemoryContext:
        return await self._memory_store.load_context(user_id=user_id, session_id=session_id)

    async def _prepare_state(
        self,
        request: "KbChatRequest",
        *,
        user_id: int,
    ) -> dict[str, Any]:
        resolved_session_id = request.session_id or self._new_run_id()
        memory = await self._load_memory_context(user_id=user_id, session_id=resolved_session_id)
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
        if not session_id or not user_id:
            return
        await self._memory_store.save_turn(
            user_id=int(user_id),
            session_id=session_id,
            team_id=state.get("team_id"),
            knowledge_base_id=state.get("knowledge_base_id"),
            assistant_id=state.get("assistant_id"),
            category_id=state.get("category_id"),
            user_message=state.get("query", ""),
            assistant_message=answer,
            assistant_metadata={
                "answer_status": answer_status,
                "log_id": log_id,
                "retrieval_status": state.get("kb_retrieval_status"),
                "retrieval_queries": list(state.get("retrieval_queries") or []),
                "retrieval_funnel": (
                    dict(state.get("retrieval_funnel") or {})
                    if isinstance(state.get("retrieval_funnel"), dict)
                    else None
                ),
                "answer_context": state.get("context"),
                "retrieved_docs": list(retrieved_docs or []),
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
    def _node_summary(node_id: str, state: dict[str, Any]) -> dict[str, Any]:
        if node_id == "retrieve":
            return {
                "retrieved_count": len(state.get("retrieved_docs", [])),
                "kb_retrieval_status": state.get("kb_retrieval_status"),
            }
        if node_id == "answer":
            return {"answer_length": len(state.get("answer", ""))}
        return {"keys": sorted(state.keys())}

    @staticmethod
    def _resolve_answer_status(result: dict[str, Any]) -> str:
        retrieval_status = result.get("kb_retrieval_status")
        if retrieval_status == "blocked_sensitive":
            return "blocked"
        if retrieval_status in {"empty_collection", "empty_knowledge_base", "no_hits"}:
            return "insufficient"
        if result.get("answer"):
            return "answered"
        return "partial"

    @staticmethod
    def _resolve_confidence(answer_status: str, retrieved_count: int) -> str | None:
        if answer_status == "blocked":
            return None
        if answer_status != "answered":
            return "low"
        if retrieved_count >= 3:
            return "high"
        if retrieved_count >= 1:
            return "medium"
        return "low"

    async def _record_log(
        self,
        *,
        state: dict[str, Any],
        result: dict[str, Any],
        latency_ms: int | None,
    ) -> int | None:
        user_id = state.get("user_id")
        if not user_id:
            return None

        try:
            async with AsyncSessionLocal() as db:
                repo = KbChatLogRepository(db)
                row = await repo.create_log(
                    user_id=int(user_id),
                    session_id=state.get("session_id"),
                    knowledge_base_id=state.get("knowledge_base_id"),
                    assistant_id=state.get("assistant_id"),
                    category_id=state.get("category_id"),
                    query=str(state.get("query") or ""),
                    answer_text=str(result.get("answer") or ""),
                    answer_status=self._resolve_answer_status(result),
                    retrieval_status=result.get("kb_retrieval_status"),
                    retrieved_count=len(result.get("retrieved_docs", []) or []),
                    latency_ms=latency_ms,
                )
                return row.id
        except Exception as exc:
            logger.exception("[KB Chat] failed to persist log: {}", exc)
            return None

    @staticmethod
    def _build_blocked_result(
        state: dict[str, Any],
        check_result: SensitiveWordCheckResult,
    ) -> dict[str, Any]:
        matched = "、".join(check_result.matched_words[:5])
        suffix = "等敏感词" if len(check_result.matched_words) > 5 else "敏感词"
        answer = (
            f"输入包含{matched}{suffix}，当前请求已被拦截。"
            if matched
            else "输入包含敏感词，当前请求已被拦截。"
        )
        return {
            **state,
            "answer": answer,
            "retrieved_docs": [],
            "kb_retrieval_status": "blocked_sensitive",
            "retrieval_queries": [],
            "retrieval_funnel": None,
            "context": "",
            "matched_sensitive_words": list(check_result.matched_words),
        }

    async def _check_sensitive_query(
        self,
        *,
        request: "KbChatRequest",
    ) -> SensitiveWordCheckResult:
        return await self._sensitive_word_service.check_text(
            scene="query",
            text=request.query,
            team_id=getattr(request, "team_id", None),
        )

    async def invoke(self, request: "KbChatRequest", *, user_id: int) -> "KbChatResponse":
        """Run the chat graph and map its result to the response schema."""

        from app.models.schemas.kb_chat import KbChatResponse

        state = await self._prepare_state(request, user_id=user_id)
        sensitive_check = await self._check_sensitive_query(request=request)
        if sensitive_check.blocked:
            result = self._build_blocked_result(state, sensitive_check)
            answer_status = self._resolve_answer_status(result)
            log_id = await self._record_log(
                state=state,
                result=result,
                latency_ms=0,
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
                confidence_level=None,
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
        answer_status = self._resolve_answer_status(result)
        log_id = await self._record_log(
            state=state,
            result=result,
            latency_ms=int((perf_counter() - started_at) * 1000),
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
            confidence_level=self._resolve_confidence(
                answer_status,
                len(result.get("retrieved_docs", []) or []),
            ),
            backend_citations=result.get("retrieved_docs", []),
            retrieved_docs=result.get("retrieved_docs", []),
            assistant_id=state.get("assistant_id"),
            assistant_name=state.get("assistant_name"),
            session_id=state.get("session_id"),
            log_id=log_id,
        )

    async def preview(self, request: "KbChatRequest", *, user_id: int) -> "KbChatResponse":
        """Run a stateless preview without persisting chat memory or logs."""

        from app.models.schemas.kb_chat import KbChatResponse

        state = self.build_initial_state(
            request,
            user_id=user_id,
            session_id=self._new_run_id(),
            chat_history=[],
            memory_summary=None,
        )
        sensitive_check = await self._check_sensitive_query(request=request)
        if sensitive_check.blocked:
            result = self._build_blocked_result(state, sensitive_check)
            answer_status = self._resolve_answer_status(result)
            return KbChatResponse(
                answer=result["answer"],
                answer_text=result["answer"],
                answer_status=answer_status,
                confidence_level=None,
                backend_citations=[],
                retrieved_docs=[],
                assistant_id=state.get("assistant_id"),
                assistant_name=state.get("assistant_name"),
                session_id=None,
                log_id=None,
            )

        result = await self._get_graph().ainvoke(state)
        answer_status = self._resolve_answer_status(result)
        return KbChatResponse(
            answer=result.get("answer", ""),
            answer_text=result.get("answer", ""),
            answer_status=answer_status,
            confidence_level=self._resolve_confidence(
                answer_status,
                len(result.get("retrieved_docs", []) or []),
            ),
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
        user_id: int,
        limit: int = 30,
    ) -> list["KbChatSessionSummary"]:
        """List persisted KB chat sessions for the current user."""

        from app.models.schemas.kb_chat import KbChatSessionSummary

        records = await self._memory_store.list_sessions(user_id=user_id, limit=limit)
        return [
            KbChatSessionSummary(
                session_id=record.session_id,
                title=record.title,
                preview=record.preview,
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
        user_id: int,
        session_id: str,
    ) -> "KbChatSessionDetail | None":
        """Load one persisted KB chat session for the current user."""

        from app.models.schemas.kb_chat import KbChatSessionDetail, KbChatSessionMessage

        record = await self._memory_store.get_session_detail(
            user_id=user_id,
            session_id=session_id,
        )
        if record is None:
            return None

        return KbChatSessionDetail(
            session_id=record.session_id,
            title=record.title,
            preview=record.preview,
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
        user_id: int,
        session_id: str,
    ) -> bool:
        """Delete one persisted KB chat session for the current user."""

        return await self._memory_store.delete_session(
            user_id=user_id,
            session_id=session_id,
        )

    async def stream(
        self,
        request: "KbChatRequest",
        *,
        user_id: int,
    ) -> AsyncGenerator[str, None]:
        """Stream graph updates and answer tokens as standardized SSE messages."""

        state = await self._prepare_state(request, user_id=user_id)
        run_id = state.get("run_id")
        graph = self._get_graph()
        started_nodes: set[str] = set()
        final_state = dict(state)
        started_at = perf_counter()

        try:
            yield emit_start(run_id, "Starting knowledge-base chat")
            sensitive_check = await self._check_sensitive_query(request=request)
            if sensitive_check.blocked:
                blocked_state = self._build_blocked_result(state, sensitive_check)
                answer_status = self._resolve_answer_status(blocked_state)
                log_id = await self._record_log(
                    state=state,
                    result=blocked_state,
                    latency_ms=0,
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
                        "confidence_level": None,
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
                        node_name = get_node_label("kb_chat", node_id)
                        if node_id not in started_nodes:
                            yield emit_node_start(
                                node_id,
                                node_name,
                                run_id,
                                message=(
                                    "Retrieving supporting documents"
                                    if node_id == "retrieve"
                                    else "Generating answer"
                                ),
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
                    node_name = get_node_label("kb_chat", node_id)
                    if node_id not in started_nodes:
                        yield emit_node_start(
                            node_id,
                            node_name,
                            run_id,
                            message="Generating answer",
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
            answer_status = self._resolve_answer_status(final_state)
            log_id = await self._record_log(
                state=state,
                result=final_state,
                latency_ms=int((perf_counter() - started_at) * 1000),
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
                    "confidence_level": self._resolve_confidence(
                        answer_status,
                        len(final_state.get("retrieved_docs", []) or []),
                    ),
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
