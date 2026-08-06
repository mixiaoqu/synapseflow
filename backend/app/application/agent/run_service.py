"""Application service for agent-routed chat."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable
from uuid import uuid4

from fastapi import HTTPException
from loguru import logger

from app.agents.runtime import AgentEventType
from app.application.agent.input_builder import AgentRunRequest, prepare_agent_input
from app.application.agent.run_recorder import AgentRunRecorder
from app.application.agent.run_trace import AgentRunTraceBuilder
from app.application.agent.runner import AgentRunner, get_agent_runner
from app.application.agent.sse_events import (
    emit_complete,
    emit_error,
    emit_event,
    emit_node_complete,
    emit_node_start,
    emit_progress,
    emit_start,
)
from app.application.agent.stream_adapter import AgentStreamAdapter
from app.application.agent.workflow_meta import (
    build_node_summary,
    get_node_label,
    get_node_progress_message,
    normalize_activity_payload,
)
from app.core.config.registry import config_registry
from app.core.llm.token_usage import summarize_token_usage, token_usage_context
from app.services.chat_memory import (
    ChatMemoryContext,
    ChatMemoryStore,
    DatabaseChatMemoryStore,
)
from app.services.chat_memory_summary import (
    ChatMemorySummaryService,
)
from app.services.content_risk_detection_service import (
    ContentRiskDetectionResult,
    get_content_risk_detection_service,
)
from app.services.document_lifecycle import VISIBLE_ASK_DOCUMENT_STATUSES

if TYPE_CHECKING:
    from app.models.schemas.kb_chat import KbChatResponse


class AgentRunService:
    """Orchestrate one Agent run across execution, safety, and persistence."""

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
        self._runner = (
            AgentRunner(graph=graph, llm_factory=llm_factory)
            if graph is not None or llm_factory is not None
            else get_agent_runner()
        )
        self._workflow_id = "agent"
        self._memory_store = memory_store or DatabaseChatMemoryStore()
        resolved_summary_service = memory_summary_service
        if resolved_summary_service is None and isinstance(
            self._memory_store,
            DatabaseChatMemoryStore,
        ):
            resolved_summary_service = ChatMemorySummaryService()
        self._recorder = AgentRunRecorder(
            memory_store=self._memory_store,
            memory_summary_service=resolved_summary_service,
        )
        self._trace_builder = AgentRunTraceBuilder()
        self._content_risk_detection_service = (
            content_risk_detection_service or get_content_risk_detection_service()
        )

    @staticmethod
    def _new_run_id() -> str:
        return uuid4().hex

    def build_initial_state(
        self,
        request: AgentRunRequest,
        *,
        user_id: int | None,
        session_id: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
        memory_summary: str | None = None,
    ) -> dict[str, Any]:
        """Build pipeline input state from the request payload."""

        resolved_session_id = session_id or request.session_id or self._new_run_id()
        agent_input = prepare_agent_input(
            query=request.query,
            session_id=resolved_session_id,
            user_id=user_id,
            team_id=request.team_id,
            external_user_id=request.external_user_id,
            external_user_name=request.external_user_name,
            product_id=request.product_id,
            project_id=request.project_id,
            project_app_id=request.project_app_id,
            knowledge_base_id=request.knowledge_base_id,
            category_id=request.category_id,
            store_id=request.store_id,
            trusted_scope=dict(request.trusted_scope or {}),
            allowed_document_statuses=list(
                request.allowed_document_statuses or VISIBLE_ASK_DOCUMENT_STATUSES
            ),
            chat_history=list(chat_history or []),
            memory_summary=memory_summary,
            assistant_id=request.assistant_id,
            assistant_name=request.assistant_name,
            assistant_llm_model_key=request.assistant_llm_model_key,
            assistant_persona_prompt=request.assistant_persona_prompt,
            assistant_rule_template=request.assistant_rule_template,
            page_context=dict(request.page_context or {}),
            page_config=dict(request.page_config or {}),
            metadata={"source_surface": request.source_surface},
        )
        # Persistence and audit code still consumes a flat application-level view.
        # Only the nested `input` object crosses the graph boundary.
        return {
            "input": agent_input,
            "workflow_id": self._workflow_id,
            "request_id": agent_input["request_id"],
            "run_id": agent_input["run_id"],
            "session_id": resolved_session_id,
            "query": agent_input["query"],
            "user_id": user_id,
            "team_id": request.team_id,
            "knowledge_base_id": request.knowledge_base_id,
            "category_id": request.category_id,
            "product_id": request.product_id,
            "project_id": request.project_id,
            "project_app_id": request.project_app_id,
            "external_user_id": request.external_user_id,
            "external_user_name": request.external_user_name,
            "assistant_id": request.assistant_id,
            "assistant_name": request.assistant_name,
            "chat_history": list(chat_history or []),
            "memory_summary": memory_summary,
        }

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
        request: AgentRunRequest,
        *,
        user_id: int | None,
    ) -> dict[str, Any]:
        resolved_session_id = request.session_id or self._new_run_id()
        memory = await self._load_memory_context(
            user_id=user_id,
            session_id=resolved_session_id,
            project_app_id=request.project_app_id,
            external_user_id=request.external_user_id,
        )
        return self.build_initial_state(
            request,
            user_id=user_id,
            session_id=resolved_session_id,
            chat_history=memory.messages,
            memory_summary=memory.summary,
        )

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

    @classmethod
    def _public_stream_error_message(cls, exc: Exception) -> str:
        if isinstance(exc, HTTPException):
            detail = exc.detail
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
        return cls._PUBLIC_STREAM_ERROR_MESSAGE

    async def _record_log(
        self,
        *,
        state: dict[str, Any],
        result: dict[str, Any],
        latency_ms: int | None,
    ) -> int | None:
        retrieved_docs = list(result.get("retrieved_docs") or [])
        trace_payload = self._trace_builder.build_log_trace_payload(
            state=state,
            result=result,
            retrieved_docs=retrieved_docs,
        )
        answer_model = self._resolve_answer_model(state)
        if answer_model is not None:
            trace_payload["answer_model"] = answer_model
        return await self._recorder.record_chat_log(
            state=state,
            result=result,
            latency_ms=latency_ms,
            trace_payload=trace_payload,
        )

    @staticmethod
    def _resolve_answer_model(state: dict[str, Any]) -> dict[str, str] | None:
        assistant = state.get("input", {}).get("assistant", {})
        model_key = str(assistant.get("model_key") or "generation").strip()
        if not model_key:
            return None
        try:
            model_config = config_registry.get_model_asset(model_key)
        except ValueError:
            try:
                model_config = config_registry.get_model_config(model_key)
            except ValueError:
                return {"key": model_key}
        return {
            "key": model_config.key,
            "model": model_config.model,
            "name": model_config.name,
            "provider": model_config.provider,
        }

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

    async def invoke(self, request: AgentRunRequest, *, user_id: int | None) -> "KbChatResponse":
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
            await self._recorder.record_content_risk_log(
                state=state,
                check_result=query_risk_check,
                checked_text=request.query,
                chat_log_id=log_id,
            )
            await self._recorder.save_turn(
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
        async with token_usage_context(scene="chat", run_id=str(state.get("run_id") or "")) as usage:
            graph_result = await self._runner.invoke(state["input"])
        graph_response = dict(graph_result.get("response") or {})
        result = {
            **state,
            **graph_result,
            **dict(graph_result.get("result") or {}),
            "answer": graph_response.get("answer", ""),
            "answer_status": graph_response.get("status", "failed"),
            "retrieved_docs": list(graph_response.get("sources") or []),
        }
        result.update(summarize_token_usage(usage))
        answer = result["answer"]
        answer_risk_check = await self._check_content_risk(scene="answer", text=answer)
        blocked_answer_text = answer
        if answer_risk_check.blocked:
            result = self._build_blocked_result({**state, **result}, answer_risk_check)
            answer = result.get("answer", "")
        answer_status = self._resolve_answer_status(result)
        total_latency_ms = int((perf_counter() - started_at) * 1000)
        self._trace_builder.log_retrieval_review(
            state=state,
            result=result,
            total_latency_ms=total_latency_ms,
        )
        log_id = await self._record_log(
            state=state,
            result=result,
            latency_ms=total_latency_ms,
        )
        await self._recorder.record_content_risk_log(
            state=state,
            check_result=answer_risk_check,
            checked_text=blocked_answer_text,
            chat_log_id=log_id,
        )
        await self._recorder.save_turn(
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

    async def preview(self, request: AgentRunRequest, *, user_id: int | None) -> "KbChatResponse":
        """Run a stateless preview without persisting chat memory or logs."""

        from app.models.schemas.kb_chat import KbChatResponse

        result = await self.execute_stateless(request, user_id=user_id)
        answer = str(result.get("answer") or "")
        return KbChatResponse(
            answer=answer,
            answer_text=answer,
            answer_status=self._resolve_answer_status(result),
            backend_citations=list(result.get("retrieved_docs") or []),
            retrieved_docs=list(result.get("retrieved_docs") or []),
            assistant_id=result.get("assistant_id"),
            assistant_name=result.get("assistant_name"),
            session_id=None,
            log_id=None,
        )

    async def execute_stateless(
        self,
        request: AgentRunRequest,
        *,
        user_id: int | None,
    ) -> dict[str, Any]:
        """Execute one Agent request without loading or writing conversation state."""

        state = self.build_initial_state(
            request,
            user_id=user_id,
            session_id=self._new_run_id(),
            chat_history=[],
            memory_summary=None,
        )
        started_at = perf_counter()
        query_risk_check = await self._check_content_risk(scene="query", text=request.query)
        if query_risk_check.blocked:
            result = self._build_blocked_result(state, query_risk_check)
            result["status"] = self._resolve_answer_status(result)
            result["latency_ms"] = int((perf_counter() - started_at) * 1000)
            result["trace"] = self._trace_builder.build_log_trace_payload(
                state=state,
                result=result,
                retrieved_docs=[],
            )
            return result

        async with token_usage_context(scene="chat", run_id=str(state.get("run_id") or "")) as usage:
            graph_result = await self._runner.invoke(state["input"])
        graph_response = dict(graph_result.get("response") or {})
        result = {
            **state,
            **graph_result,
            **dict(graph_result.get("result") or {}),
            "answer": graph_response.get("answer", ""),
            "answer_status": graph_response.get("status", "failed"),
            "retrieved_docs": list(graph_response.get("sources") or []),
        }
        result.update(summarize_token_usage(usage))
        answer_risk_check = await self._check_content_risk(
            scene="answer",
            text=str(result.get("answer") or ""),
        )
        if answer_risk_check.blocked:
            result = self._build_blocked_result({**state, **result}, answer_risk_check)
        result["answer_status"] = self._resolve_answer_status(result)
        result["status"] = result["answer_status"]
        result["latency_ms"] = int((perf_counter() - started_at) * 1000)
        result["trace"] = self._trace_builder.build_log_trace_payload(
            state=state,
            result=result,
            retrieved_docs=list(result.get("retrieved_docs") or []),
        )
        return result

    async def stream(
        self,
        request: AgentRunRequest,
        *,
        user_id: int | None,
    ) -> AsyncGenerator[str, None]:
        """Stream graph updates and answer tokens as standardized SSE messages."""

        state = await self._prepare_state(request, user_id=user_id)
        run_id = state.get("run_id")
        workflow_id = str(state.get("workflow_id") or self._workflow_id)
        started_nodes: set[tuple[str, str]] = set()
        final_state = dict(state)
        started_at = perf_counter()
        usage_context = token_usage_context(scene="chat", run_id=str(run_id or ""))
        usage = await usage_context.__aenter__()

        try:
            yield emit_start(run_id, "开始处理请求", workflow_id=workflow_id)
            query_risk_check = await self._check_content_risk(scene="query", text=request.query)
            if query_risk_check.blocked:
                blocked_state = self._build_blocked_result(state, query_risk_check)
                blocked_state.update(summarize_token_usage(usage))
                answer_status = self._resolve_answer_status(blocked_state)
                log_id = await self._record_log(
                    state=state,
                    result=blocked_state,
                    latency_ms=0,
                )
                await self._recorder.record_content_risk_log(
                    state=state,
                    check_result=query_risk_check,
                    checked_text=request.query,
                    chat_log_id=log_id,
                )
                await self._recorder.save_turn(
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

            async for chunk in self._runner.stream(state["input"]):
                chunk_type, chunk_data = AgentStreamAdapter.parse_chunk(chunk)

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
                        yield emit_event(
                            AgentEventType.TOKEN,
                            {"text": text},
                            workflow_id=node_workflow_id,
                            node_id=node_id,
                            node_name=node_name,
                            run_id=run_id,
                        )

            graph_response = dict(final_state.get("response") or {})
            final_state.update(dict(final_state.get("result") or {}))
            answer = str(graph_response.get("answer") or "")
            final_state["answer"] = answer
            final_state["answer_status"] = str(graph_response.get("status") or "failed")
            final_state["retrieved_docs"] = list(graph_response.get("sources") or [])
            final_state.update(summarize_token_usage(usage))
            answer_risk_check = await self._check_content_risk(scene="answer", text=answer)
            blocked_answer_text = answer
            if answer_risk_check.blocked:
                final_state = self._build_blocked_result(final_state, answer_risk_check)
                answer = final_state.get("answer", "")
            answer_status = self._resolve_answer_status(final_state)
            total_latency_ms = int((perf_counter() - started_at) * 1000)
            self._trace_builder.log_retrieval_review(
                state=state,
                result=final_state,
                total_latency_ms=total_latency_ms,
            )
            log_id = await self._record_log(
                state=state,
                result=final_state,
                latency_ms=total_latency_ms,
            )
            await self._recorder.record_content_risk_log(
                state=state,
                check_result=answer_risk_check,
                checked_text=blocked_answer_text,
                chat_log_id=log_id,
            )
            await self._recorder.save_turn(
                state=final_state,
                answer=answer,
                answer_status=answer_status,
                log_id=log_id,
                retrieved_docs=list(final_state.get("retrieved_docs", []) or []),
            )
            yield emit_complete(
                run_id,
                AgentStreamAdapter.complete_payload(
                    response={
                        "answer": answer,
                        "status": answer_status,
                        "sources": final_state.get("retrieved_docs", []),
                    },
                    assistant_id=state.get("assistant_id"),
                    assistant_name=state.get("assistant_name"),
                    session_id=state.get("session_id"),
                    log_id=log_id,
                ),
                workflow_id=workflow_id,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("[Agent Chat] stream failed after execution stage: {}", exc)
            yield emit_error(
                run_id, self._public_stream_error_message(exc), workflow_id=workflow_id
            )
        finally:
            await usage_context.__aexit__(None, None, None)


agent_run_service: AgentRunService | None = None


def get_agent_run_service() -> AgentRunService:
    global agent_run_service
    if agent_run_service is None:
        agent_run_service = AgentRunService()
    return agent_run_service
