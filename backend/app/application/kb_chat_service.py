"""Application service for end-user knowledge-base chat."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable

from app.agents.nodes.kb_chat import user_kb_retrieve_node
from app.agents.nodes.kb_chat.generate_answer import (
    generate_kb_chat_answer_text,
    stream_kb_chat_answer_text,
)
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

if TYPE_CHECKING:
    from app.models.schemas.kb_chat import KbChatRequest, KbChatResponse


class KbChatService(BaseAgentService):
    """Encapsulates end-user knowledge-base chat orchestration."""

    def __init__(self, llm_factory: Callable[[], Any] | None = None):
        if llm_factory is None:
            from app.core.llm import get_llm_for_generation

            llm_factory = get_llm_for_generation
        self._llm_factory = llm_factory

    def build_initial_state(
        self,
        request: "KbChatRequest",
        *,
        user_id: int,
    ) -> dict[str, Any]:
        """Build pipeline input state from the request payload."""

        context = self.build_context(
            user_id=user_id,
            knowledge_base_id=request.knowledge_base_id,
            category_id=getattr(request, "category_id", None),
            request_id=request.session_id,
            metadata={"workflow": "kb_chat"},
        )
        return self.build_state(
            context,
            {
                "query": request.query,
                "retrieved_docs": [],
                "context": "",
                "answer": "",
                "kb_retrieval_status": None,
            },
        )

    async def _retrieve(self, state: dict[str, Any]) -> dict[str, Any]:
        retrieve_out = await user_kb_retrieve_node(state)
        state.update(retrieve_out)
        return state

    async def invoke(self, request: "KbChatRequest", *, user_id: int) -> "KbChatResponse":
        """Run the chat pipeline and map its result to the response schema."""

        from app.models.schemas.kb_chat import KbChatResponse

        state = await self._retrieve(self.build_initial_state(request, user_id=user_id))
        state["answer"] = await generate_kb_chat_answer_text(
            state,
            llm_factory=self._llm_factory,
        )
        return KbChatResponse(
            answer=state.get("answer", ""),
            retrieved_docs=state.get("retrieved_docs", []),
            session_id=request.session_id,
        )

    async def stream(
        self,
        request: "KbChatRequest",
        *,
        user_id: int,
    ) -> AsyncGenerator[str, None]:
        """Stream retrieved docs and answer tokens as SSE messages."""

        state = self.build_initial_state(request, user_id=user_id)
        run_id = state.get("run_id")

        try:
            yield emit_start(run_id, "Starting knowledge-base chat")
            yield emit_node_start(
                "retrieve",
                get_node_label("kb_chat", "retrieve"),
                run_id,
                message="Retrieving supporting documents",
            )

            state = await self._retrieve(state)
            yield emit_event(
                AgentEventType.RETRIEVED,
                {"retrieved_docs": state.get("retrieved_docs", [])},
                node_id="retrieve",
                node_name=get_node_label("kb_chat", "retrieve"),
                run_id=run_id,
            )
            yield emit_node_complete(
                "retrieve",
                get_node_label("kb_chat", "retrieve"),
                run_id,
                {
                    "retrieved_count": len(state.get("retrieved_docs", [])),
                    "kb_retrieval_status": state.get("kb_retrieval_status"),
                },
            )
            await asyncio.sleep(0)

            yield emit_node_start(
                "answer",
                get_node_label("kb_chat", "answer"),
                run_id,
                message="Generating answer",
            )

            full_answer: list[str] = []
            async for text in stream_kb_chat_answer_text(
                state,
                llm_factory=self._llm_factory,
            ):
                full_answer.append(text)
                yield emit_event(
                    AgentEventType.TOKEN,
                    {"text": text},
                    node_id="answer",
                    node_name=get_node_label("kb_chat", "answer"),
                    run_id=run_id,
                )

            state["answer"] = "".join(full_answer)
            await asyncio.sleep(0)

            yield emit_node_complete(
                "answer",
                get_node_label("kb_chat", "answer"),
                run_id,
                {"answer_length": len(state["answer"])},
            )
            yield emit_complete(
                run_id,
                {
                    "answer": state["answer"],
                    "retrieved_docs": state.get("retrieved_docs", []),
                    "session_id": request.session_id,
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
