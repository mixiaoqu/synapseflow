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


def test_kb_chat_stream_emits_standardized_envelopes():
    service = KbChatService(llm_factory=lambda: None)

    async def fake_retrieve(state: dict) -> dict:
        state.update(
            {
                "retrieved_docs": [
                    {
                        "content": "LangGraph is a stateful orchestration framework.",
                        "metadata": {"document_title": "LangGraph Intro"},
                    }
                ],
                "kb_retrieval_status": "ok",
                "context": "LangGraph is a stateful orchestration framework.",
            }
        )
        return state

    async def fake_answer_stream(state: dict, **_: object):
        for chunk in ["LangGraph ", "helps ", "compose flows."]:
            yield chunk

    service._retrieve = fake_retrieve  # type: ignore[method-assign]

    import app.application.kb_chat_service as kb_chat_service_module

    original_stream = kb_chat_service_module.stream_kb_chat_answer_text
    kb_chat_service_module.stream_kb_chat_answer_text = fake_answer_stream
    try:
        request = SimpleNamespace(
            query="What is LangGraph?",
            knowledge_base_id=9,
            category_id=4,
            session_id=None,
        )

        async def collect() -> list[str]:
            return [event async for event in service.stream(request, user_id=42)]

        events = asyncio.run(collect())
    finally:
        kb_chat_service_module.stream_kb_chat_answer_text = original_stream

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
    service = KbChatService(llm_factory=lambda: None)
    request = SimpleNamespace(
        query="退款规则是什么",
        knowledge_base_id=3,
        category_id=7,
        session_id="session-1",
    )

    state = service.build_initial_state(request, user_id=99)

    assert state["knowledge_base_id"] == 3
    assert state["category_id"] == 7
    assert state["query"] == "退款规则是什么"
