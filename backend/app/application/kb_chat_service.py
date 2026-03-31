"""Application service for end-user knowledge-base chat."""

import asyncio
import json
from typing import Any, AsyncGenerator, Callable, Dict

from app.agents.nodes.kb_chat import user_kb_retrieve_node
from app.agents.nodes.kb_chat.generate_answer import (
    generate_kb_chat_answer_text,
    stream_kb_chat_answer_text,
)
from app.core.llm import get_llm_for_generation
from app.models.schemas.kb_chat import KbChatRequest, KbChatResponse

SSE_EVENT = "message"


class KbChatService:
    """Encapsulates end-user knowledge-base chat orchestration."""

    def __init__(self, llm_factory: Callable[[], Any] = get_llm_for_generation):
        self._llm_factory = llm_factory

    @staticmethod
    def build_initial_state(request: KbChatRequest) -> Dict[str, Any]:
        """Build pipeline input state from the request payload."""
        return {
            "messages": [],
            "query": request.query,
            "collection_id": request.collection_id,
            "retrieved_docs": [],
            "context": "",
            "answer": "",
        }

    @staticmethod
    def _envelope(message_type: str, data: Dict[str, Any]) -> str:
        body = {"type": message_type, "data": data}
        return "event: %s\ndata: %s\n\n" % (
            SSE_EVENT,
            json.dumps(body, ensure_ascii=False),
        )

    async def _retrieve(self, state: Dict[str, Any]) -> Dict[str, Any]:
        retrieve_out = await user_kb_retrieve_node(state)
        state.update(retrieve_out)
        return state

    async def invoke(self, request: KbChatRequest) -> KbChatResponse:
        """Run the chat pipeline and map its result to the response schema."""
        state = await self._retrieve(self.build_initial_state(request))
        state["answer"] = await generate_kb_chat_answer_text(
            state,
            llm_factory=self._llm_factory,
        )
        return KbChatResponse(
            answer=state.get("answer", ""),
            retrieved_docs=state.get("retrieved_docs", []),
            session_id=request.session_id,
        )

    async def stream(self, request: KbChatRequest) -> AsyncGenerator[str, None]:
        """Stream retrieved docs and answer tokens as SSE messages."""
        try:
            state = await self._retrieve(self.build_initial_state(request))
            yield self._envelope(
                "retrieved",
                {"retrieved_docs": state.get("retrieved_docs", [])},
            )
            await asyncio.sleep(0)

            full_answer: list[str] = []
            async for text in stream_kb_chat_answer_text(
                state,
                llm_factory=self._llm_factory,
            ):
                full_answer.append(text)
                yield self._envelope("token", {"text": text})
            state["answer"] = "".join(full_answer)
            await asyncio.sleep(0)

            yield self._envelope("done", {"answer": state["answer"]})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield self._envelope("error", {"message": str(exc)})


kb_chat_service = KbChatService()
