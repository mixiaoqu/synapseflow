"""Application service for end-user knowledge-base chat."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable

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
from app.services.chat_memory import (
    ChatMemoryContext,
    ChatMemoryStore,
    DatabaseChatMemoryStore,
)

if TYPE_CHECKING:
    from app.models.schemas.kb_chat import KbChatRequest, KbChatResponse


class KbChatService(BaseAgentService):
    """Encapsulates end-user knowledge-base chat orchestration."""

    def __init__(
        self,
        llm_factory: Callable[[], Any] | None = None,
        graph: Any | None = None,
        memory_store: ChatMemoryStore | None = None,
    ):
        if llm_factory is None:
            from app.core.llm import get_llm_for_generation

            llm_factory = get_llm_for_generation

        self._llm_factory = llm_factory
        self._graph = graph
        self._memory_store = memory_store or DatabaseChatMemoryStore()

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
                "chat_history": history,
                "memory_summary": memory_summary,
                "retrieval_queries": [],
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
    ) -> None:
        session_id = state.get("session_id")
        user_id = state.get("user_id")
        if not session_id or not user_id:
            return
        await self._memory_store.save_turn(
            user_id=int(user_id),
            session_id=session_id,
            knowledge_base_id=state.get("knowledge_base_id"),
            category_id=state.get("category_id"),
            user_message=state.get("query", ""),
            assistant_message=answer,
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

    async def invoke(self, request: "KbChatRequest", *, user_id: int) -> "KbChatResponse":
        """Run the chat graph and map its result to the response schema."""

        from app.models.schemas.kb_chat import KbChatResponse

        state = await self._prepare_state(request, user_id=user_id)
        result = await self._get_graph().ainvoke(state)
        answer = result.get("answer", "")
        await self._save_turn(state=state, answer=answer)
        return KbChatResponse(
            answer=answer,
            retrieved_docs=result.get("retrieved_docs", []),
            session_id=state.get("session_id"),
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

        try:
            yield emit_start(run_id, "Starting knowledge-base chat")

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
            await self._save_turn(state=state, answer=answer)
            yield emit_complete(
                run_id,
                {
                    "answer": answer,
                    "retrieved_docs": final_state.get("retrieved_docs", []),
                    "session_id": state.get("session_id"),
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield emit_error(run_id, str(exc))


kb_chat_service: KbChatService | None = None


def get_kb_chat_service() -> KbChatService:
    global kb_chat_service
    if kb_chat_service is None:
        kb_chat_service = KbChatService()
    return kb_chat_service
