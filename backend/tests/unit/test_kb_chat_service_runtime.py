import asyncio
import json
from types import SimpleNamespace

from app.application.kb_chat_service import KbChatService


def _decode_sse_payloads(events: list[str]) -> list[dict]:
    payloads: list[dict] = []
    for event in events:
        raw = event.split("data: ", 1)[1].strip()
        payloads.append(json.loads(raw))
    return payloads


class FakeKbChatGraph:
    async def ainvoke(self, state: dict) -> dict:
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


def test_kb_chat_invoke_uses_graph_result():
    service = KbChatService(llm_factory=lambda: None, graph=FakeKbChatGraph())
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


def test_kb_chat_stream_emits_standardized_envelopes():
    service = KbChatService(llm_factory=lambda: None, graph=FakeKbChatGraph())
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


def test_kb_chat_build_initial_state_keeps_category_id():
    service = KbChatService(llm_factory=lambda: None, graph=FakeKbChatGraph())
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
