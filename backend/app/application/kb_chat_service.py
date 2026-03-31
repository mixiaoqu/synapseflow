"""Application service for end-user knowledge-base chat."""

import asyncio
import json
from typing import Any, AsyncGenerator, Callable, Dict

from app.agents.graphs.kb_chat_graph import create_kb_chat_graph
from app.agents.nodes.kb_chat import user_kb_retrieve_node
from app.agents.nodes.kb_chat.generate_answer import should_skip_kb_llm
from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt
from app.core.llm import get_llm_for_generation
from app.models.schemas.kb_chat import KbChatRequest, KbChatResponse

SSE_EVENT = "message"


class KbChatService:
    """Encapsulates end-user knowledge-base chat orchestration."""

    def __init__(
        self,
        graph: Any | None = None,
        llm_factory: Callable[[], Any] = get_llm_for_generation,
    ):
        self._graph = graph or create_kb_chat_graph()
        self._llm_factory = llm_factory

    @staticmethod
    def build_initial_state(request: KbChatRequest) -> Dict[str, Any]:
        """Build graph input state from the request payload."""
        return {
            "messages": [],
            "query": request.query,
            "collection_id": request.collection_id,
            "retrieved_docs": [],
            "context": "",
            "answer": "",
        }

    @staticmethod
    def _stream_chunk_text(chunk: Any) -> str:
        content = getattr(chunk, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            return "".join(parts)
        return ""

    @staticmethod
    def _envelope(message_type: str, data: Dict[str, Any]) -> str:
        body = {"type": message_type, "data": data}
        return "event: %s\ndata: %s\n\n" % (
            SSE_EVENT,
            json.dumps(body, ensure_ascii=False),
        )

    async def invoke(self, request: KbChatRequest) -> KbChatResponse:
        """Run the chat graph and map its result to the response schema."""
        result = await self._graph.ainvoke(self.build_initial_state(request))
        return KbChatResponse(
            answer=result.get("answer", ""),
            retrieved_docs=result.get("retrieved_docs", []),
            session_id=request.session_id,
        )

    async def stream(self, request: KbChatRequest) -> AsyncGenerator[str, None]:
        """Stream retrieved docs and answer tokens as SSE messages."""
        state = self.build_initial_state(request)
        try:
            retrieve_out = await user_kb_retrieve_node(state)
            state.update(retrieve_out)
            yield self._envelope(
                "retrieved",
                {"retrieved_docs": state.get("retrieved_docs", [])},
            )
            await asyncio.sleep(0)

            skip_reply = should_skip_kb_llm(state)
            if skip_reply:
                yield self._envelope("token", {"text": skip_reply})
                yield self._envelope("done", {"answer": skip_reply})
                return

            prompt = build_kb_chat_answer_prompt(
                state.get("query", ""),
                state.get("context", ""),
            )
            llm = self._llm_factory()
            full_answer: list[str] = []
            async for chunk in llm.astream(prompt):
                text = self._stream_chunk_text(chunk)
                if text:
                    full_answer.append(text)
                    yield self._envelope("token", {"text": text})
            await asyncio.sleep(0)

            yield self._envelope("done", {"answer": "".join(full_answer)})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield self._envelope("error", {"message": str(exc)})


kb_chat_service = KbChatService()
