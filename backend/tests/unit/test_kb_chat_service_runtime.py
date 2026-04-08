import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

from app.application.kb_chat_service import KbChatService
from app.services.chat_memory import (
    ChatMemoryContext,
    ChatSessionDetailRecord,
    ChatSessionSummaryRecord,
)


def _decode_sse_payloads(events: list[str]) -> list[dict]:
    payloads: list[dict] = []
    for event in events:
        raw = event.split("data: ", 1)[1].strip()
        payloads.append(json.loads(raw))
    return payloads


class FakeKbChatGraph:
    def __init__(self) -> None:
        self.last_state = None

    async def ainvoke(self, state: dict) -> dict:
        self.last_state = state
        return {
            **state,
            "retrieved_docs": [
                {
                    "content": "LangGraph is a stateful orchestration framework.",
                    "metadata": {"document_title": "LangGraph Intro"},
                }
            ],
            "kb_retrieval_status": "ok",
            "context": "LangGraph is a stateful orchestration framework.",
            "answer": "LangGraph helps compose flows.",
        }

    async def astream(self, state: dict, *, stream_mode: list[str], version: str):
        self.last_state = state
        assert stream_mode == ["updates", "custom"]
        assert version == "v2"
        yield {
            "type": "updates",
            "data": {
                "retrieve": {
                    "retrieved_docs": [
                        {
                            "content": "LangGraph is a stateful orchestration framework.",
                            "metadata": {"document_title": "LangGraph Intro"},
                        }
                    ],
                    "kb_retrieval_status": "ok",
                    "context": "LangGraph is a stateful orchestration framework.",
                }
            },
        }
        yield {"type": "custom", "data": {"node_id": "answer", "text": "LangGraph "}}
        yield {"type": "custom", "data": {"node_id": "answer", "text": "helps "}}
        yield {"type": "custom", "data": {"node_id": "answer", "text": "compose flows."}}
        yield {
            "type": "updates",
            "data": {
                "answer": {
                    "answer": "LangGraph helps compose flows.",
                    "messages": [
                        {"role": "assistant", "content": "LangGraph helps compose flows."}
                    ],
                }
            },
        }


class FakeChatMemoryStore:
    def __init__(self, context: ChatMemoryContext | None = None) -> None:
        self.context = context or ChatMemoryContext(messages=[], summary=None)
        self.load_calls = []
        self.save_calls = []
        self.list_calls = []
        self.detail_calls = []
        now = datetime.utcnow()
        self.sessions = [
            ChatSessionSummaryRecord(
                session_id="session-1",
                title="What is LangGraph?",
                preview="LangGraph helps compose flows.",
                knowledge_base_id=9,
                knowledge_base_name="Product Docs",
                category_id=4,
                category_name="Guides",
                message_count=2,
                created_at=now,
                updated_at=now,
            )
        ]
        self.session_detail = ChatSessionDetailRecord(
            session_id="session-1",
            title="What is LangGraph?",
            preview="LangGraph helps compose flows.",
            knowledge_base_id=9,
            knowledge_base_name="Product Docs",
            category_id=4,
            category_name="Guides",
            message_count=2,
            created_at=now,
            updated_at=now,
            messages=[
                {
                    "role": "user",
                    "content": "What is LangGraph?",
                    "created_at": now,
                },
                {
                    "role": "assistant",
                    "content": "LangGraph helps compose flows.",
                    "created_at": now,
                },
            ],
        )

    async def load_context(self, *, user_id: int, session_id: str) -> ChatMemoryContext:
        self.load_calls.append({"user_id": user_id, "session_id": session_id})
        return self.context

    async def save_turn(
        self,
        *,
        user_id: int,
        session_id: str,
        knowledge_base_id: int | None,
        category_id: int | None,
        user_message: str,
        assistant_message: str,
    ) -> None:
        self.save_calls.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "knowledge_base_id": knowledge_base_id,
                "category_id": category_id,
                "user_message": user_message,
                "assistant_message": assistant_message,
            }
        )

    async def list_sessions(self, *, user_id: int, limit: int = 30):
        self.list_calls.append({"user_id": user_id, "limit": limit})
        return self.sessions[:limit]

    async def get_session_detail(self, *, user_id: int, session_id: str):
        self.detail_calls.append({"user_id": user_id, "session_id": session_id})
        if self.session_detail.session_id != session_id:
            return None
        return self.session_detail


def test_kb_chat_invoke_uses_graph_result():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore(
        ChatMemoryContext(
            messages=[
                {"role": "user", "content": "What is LangGraph?"},
                {"role": "assistant", "content": "It is an orchestration framework."},
            ],
            summary="The user is asking about LangGraph basics.",
        )
    )
    service = KbChatService(llm_factory=lambda: None, graph=graph, memory_store=memory_store)
    request = SimpleNamespace(
        query="What is LangGraph?",
        knowledge_base_id=9,
        category_id=4,
        session_id="session-1",
    )

    response = asyncio.run(service.invoke(request, user_id=42))

    assert response.answer == "LangGraph helps compose flows."
    assert response.retrieved_docs[0]["metadata"]["document_title"] == "LangGraph Intro"
    assert response.session_id == "session-1"
    assert graph.last_state["chat_history"][0]["role"] == "user"
    assert graph.last_state["memory_summary"] == "The user is asking about LangGraph basics."
    assert memory_store.load_calls == [{"user_id": 42, "session_id": "session-1"}]
    assert memory_store.save_calls[0]["assistant_message"] == "LangGraph helps compose flows."


def test_kb_chat_stream_emits_standardized_envelopes():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore()
    service = KbChatService(llm_factory=lambda: None, graph=graph, memory_store=memory_store)
    request = SimpleNamespace(
        query="What is LangGraph?",
        knowledge_base_id=9,
        category_id=4,
        session_id=None,
    )

    async def collect() -> list[str]:
        return [event async for event in service.stream(request, user_id=42)]

    events = asyncio.run(collect())
    payloads = _decode_sse_payloads(events)
    types = [payload["type"] for payload in payloads]

    assert types == [
        "start",
        "node_start",
        "retrieved",
        "node_complete",
        "node_start",
        "token",
        "token",
        "token",
        "node_complete",
        "complete",
    ]
    assert all(payload["run_id"] for payload in payloads)
    assert payloads[2]["data"]["retrieved_docs"][0]["metadata"]["document_title"] == (
        "LangGraph Intro"
    )
    assert payloads[-1]["data"]["answer"] == "LangGraph helps compose flows."
    assert payloads[-1]["data"]["session_id"]
    assert memory_store.load_calls[0]["session_id"] == payloads[-1]["data"]["session_id"]
    assert memory_store.save_calls[0]["assistant_message"] == "LangGraph helps compose flows."
    assert graph.last_state["session_id"] == payloads[-1]["data"]["session_id"]


def test_kb_chat_build_initial_state_keeps_category_id():
    service = KbChatService(
        llm_factory=lambda: None,
        graph=FakeKbChatGraph(),
        memory_store=FakeChatMemoryStore(),
    )
    request = SimpleNamespace(
        query="What is the refund policy?",
        knowledge_base_id=3,
        category_id=7,
        session_id="session-1",
    )

    state = service.build_initial_state(request, user_id=99)

    assert state["knowledge_base_id"] == 3
    assert state["category_id"] == 7
    assert state["query"] == "What is the refund policy?"
    assert state["session_id"] == "session-1"
    assert state["chat_history"] == []


def test_kb_chat_list_sessions_returns_history_for_user():
    memory_store = FakeChatMemoryStore()
    service = KbChatService(llm_factory=lambda: None, graph=FakeKbChatGraph(), memory_store=memory_store)

    sessions = asyncio.run(service.list_sessions(user_id=42, limit=10))

    assert len(sessions) == 1
    assert sessions[0].session_id == "session-1"
    assert sessions[0].knowledge_base_name == "Product Docs"
    assert memory_store.list_calls == [{"user_id": 42, "limit": 10}]


def test_kb_chat_get_session_returns_persisted_messages():
    memory_store = FakeChatMemoryStore()
    service = KbChatService(llm_factory=lambda: None, graph=FakeKbChatGraph(), memory_store=memory_store)

    session = asyncio.run(service.get_session(user_id=42, session_id="session-1"))

    assert session is not None
    assert session.session_id == "session-1"
    assert session.messages[0].role == "user"
    assert session.messages[1].content == "LangGraph helps compose flows."
    assert memory_store.detail_calls == [{"user_id": 42, "session_id": "session-1"}]
