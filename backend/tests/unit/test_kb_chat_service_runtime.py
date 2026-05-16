import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

from app.api.v1.endpoints.ask import _build_log_detail_response
from app.application.kb_chat_service import KbChatService
from app.repositories.kb_chat_log_repository import (
    KbChatDiagnosticDocRecord,
    KbChatDiagnosticMessageRecord,
    KbChatLogDetailRecord,
)
from app.services.chat_memory import (
    ChatMemoryContext,
    ChatSessionDetailRecord,
    ChatSessionSummaryRecord,
)
from app.services.document_lifecycle import (
    PREVIEW_ASK_DOCUMENT_STATUSES,
    RETRIEVAL_VERSION_CURRENT,
    RETRIEVAL_VERSION_LIVE,
    VISIBLE_ASK_DOCUMENT_STATUSES,
)
from app.services.sensitive_word_service import SensitiveWordCheckResult


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
                    "metadata": {
                        "document_id": 11,
                        "chunk_index": 0,
                        "document_title": "LangGraph Intro",
                    },
                }
            ],
            "retrieval_queries": ["What is LangGraph?", "LangGraph basics"],
            "retrieval_trace": {
                "text": {"text_hits": 1},
                "graph": {"graph_hits": 0, "empty_reason": "no_hits"},
                "final_hits": 1,
                "empty_reason": None,
                "final_context_docs": 1,
            },
            "retrieval_funnel": {
                "mode": "hybrid",
                "query_count": 2,
                "rewritten_queries": [
                    {"query": "What is LangGraph?", "chunk_count": 4},
                    {"query": "LangGraph basics", "chunk_count": 3},
                ],
                "stages": [
                    {"key": "recalled_candidates", "label": "改写后总召回", "chunk_count": 7},
                    {"key": "merged_candidates", "label": "融合去重后", "chunk_count": 5},
                    {"key": "reranked_candidates", "label": "重排过滤后", "chunk_count": 2},
                    {"key": "context_chunks", "label": "进入回答上下文", "chunk_count": 1},
                ],
            },
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
                            "metadata": {
                                "document_id": 11,
                                "chunk_index": 0,
                                "document_title": "LangGraph Intro",
                            },
                        }
                    ],
                    "retrieval_queries": ["What is LangGraph?", "LangGraph basics"],
                    "retrieval_trace": {
                        "text": {"text_hits": 1},
                        "graph": {"graph_hits": 0, "empty_reason": "no_hits"},
                        "final_hits": 1,
                        "empty_reason": None,
                        "final_context_docs": 1,
                    },
                    "retrieval_funnel": {
                        "mode": "hybrid",
                        "query_count": 2,
                        "rewritten_queries": [
                            {"query": "What is LangGraph?", "chunk_count": 4},
                            {"query": "LangGraph basics", "chunk_count": 3},
                        ],
                        "stages": [
                            {
                                "key": "recalled_candidates",
                                "label": "改写后总召回",
                                "chunk_count": 7,
                            },
                            {"key": "merged_candidates", "label": "融合去重后", "chunk_count": 5},
                            {"key": "reranked_candidates", "label": "重排过滤后", "chunk_count": 2},
                            {"key": "context_chunks", "label": "进入回答上下文", "chunk_count": 1},
                        ],
                    },
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
        self.delete_calls = []
        now = datetime.utcnow()
        self.sessions = [
            ChatSessionSummaryRecord(
                session_id="session-1",
                title="What is LangGraph?",
                preview="LangGraph helps compose flows.",
                product_id=None,
                project_id=None,
                project_app_id=None,
                external_user_id=None,
                external_user_name=None,
                team_id=2,
                knowledge_base_id=9,
                knowledge_base_branch_ids=[],
                knowledge_base_name="Product Docs",
                assistant_id=5,
                assistant_name="Project Assistant",
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
            product_id=None,
            project_id=None,
            project_app_id=None,
            external_user_id=None,
            external_user_name=None,
            team_id=2,
            knowledge_base_id=9,
            knowledge_base_branch_ids=[],
            knowledge_base_name="Product Docs",
            assistant_id=5,
            assistant_name="Project Assistant",
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

    async def load_context(
        self,
        *,
        user_id: int,
        session_id: str,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> ChatMemoryContext:
        self.load_calls.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "project_app_id": project_app_id,
                "external_user_id": external_user_id,
            }
        )
        return self.context

    async def save_turn(
        self,
        *,
        user_id: int,
        session_id: str,
        product_id: int | None = None,
        project_id: int | None = None,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
        external_user_name: str | None = None,
        team_id: int | None,
        knowledge_base_id: int | None,
        knowledge_base_branch_ids: list[int] | None = None,
        assistant_id: int | None,
        category_id: int | None,
        user_message: str,
        assistant_message: str,
        assistant_metadata: dict | None = None,
    ) -> None:
        self.save_calls.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "product_id": product_id,
                "project_id": project_id,
                "project_app_id": project_app_id,
                "external_user_id": external_user_id,
                "external_user_name": external_user_name,
                "team_id": team_id,
                "knowledge_base_id": knowledge_base_id,
                "knowledge_base_branch_ids": knowledge_base_branch_ids or [],
                "assistant_id": assistant_id,
                "category_id": category_id,
                "user_message": user_message,
                "assistant_message": assistant_message,
                "assistant_metadata": assistant_metadata,
            }
        )

    async def list_sessions(
        self,
        *,
        user_id: int,
        limit: int = 30,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ):
        self.list_calls.append(
            {
                "user_id": user_id,
                "limit": limit,
                "project_app_id": project_app_id,
                "external_user_id": external_user_id,
            }
        )
        return self.sessions[:limit]

    async def get_session_detail(
        self,
        *,
        user_id: int,
        session_id: str,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ):
        self.detail_calls.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "project_app_id": project_app_id,
                "external_user_id": external_user_id,
            }
        )
        if self.session_detail.session_id != session_id:
            return None
        return self.session_detail

    async def delete_session(
        self,
        *,
        user_id: int,
        session_id: str,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> bool:
        self.delete_calls.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "project_app_id": project_app_id,
                "external_user_id": external_user_id,
            }
        )
        if self.session_detail.session_id != session_id:
            return False
        self.sessions = [item for item in self.sessions if item.session_id != session_id]
        return True


class FakeSensitiveWordService:
    def __init__(self, blocked: bool = False, matched_words: list[str] | None = None) -> None:
        self.blocked = blocked
        self.matched_words = matched_words or ["secret"]
        self.calls = []

    async def check_text(self, *, scene: str, text: str, team_id: int | None):
        self.calls.append({"scene": scene, "text": text, "team_id": team_id})
        return SensitiveWordCheckResult(
            blocked=self.blocked,
            matched_words=list(self.matched_words if self.blocked else []),
            scene=scene,
            reason="Matched sensitive words" if self.blocked else None,
        )


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
    service = KbChatService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        sensitive_word_service=FakeSensitiveWordService(blocked=False),
    )
    request = SimpleNamespace(
        query="What is LangGraph?",
        knowledge_base_id=9,
        category_id=4,
        session_id="session-1",
    )

    response = asyncio.run(service.invoke(request, user_id=42))

    assert response.answer == "LangGraph helps compose flows."
    assert response.answer_text == "LangGraph helps compose flows."
    assert response.answer_status == "answered"
    assert response.assistant_id is None
    assert response.retrieved_docs[0]["metadata"]["document_title"] == "LangGraph Intro"
    assert response.session_id == "session-1"
    assert graph.last_state["chat_history"][0]["role"] == "user"
    assert graph.last_state["memory_summary"] == "The user is asking about LangGraph basics."
    assert memory_store.load_calls == [
        {
            "user_id": 42,
            "session_id": "session-1",
            "project_app_id": None,
            "external_user_id": None,
        }
    ]
    assert memory_store.save_calls[0]["assistant_message"] == "LangGraph helps compose flows."
    assert memory_store.save_calls[0]["assistant_metadata"]["retrieval_queries"] == [
        "What is LangGraph?",
        "LangGraph basics",
    ]


def test_kb_chat_stream_emits_standardized_envelopes():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore()
    service = KbChatService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        sensitive_word_service=FakeSensitiveWordService(blocked=False),
    )
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
    assert payloads[-1]["data"]["answer_status"] == "answered"
    assert payloads[-1]["data"]["session_id"]
    assert memory_store.load_calls[0]["session_id"] == payloads[-1]["data"]["session_id"]
    assert memory_store.save_calls[0]["assistant_message"] == "LangGraph helps compose flows."
    assert memory_store.save_calls[0]["assistant_metadata"]["retrieval_queries"] == [
        "What is LangGraph?",
        "LangGraph basics",
    ]
    assert graph.last_state["session_id"] == payloads[-1]["data"]["session_id"]


def test_kb_chat_invoke_blocks_sensitive_query_before_graph_runs():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore()
    sensitive_service = FakeSensitiveWordService(blocked=True, matched_words=["internal roadmap"])
    service = KbChatService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        sensitive_word_service=sensitive_service,
    )
    request = SimpleNamespace(
        query="Show me the internal roadmap",
        team_id=7,
        knowledge_base_id=9,
        category_id=4,
        session_id="session-1",
    )

    response = asyncio.run(service.invoke(request, user_id=42))

    assert response.answer_status == "blocked"
    assert response.answer_text.startswith("输入包含")
    assert response.retrieved_docs == []
    assert graph.last_state is None
    assert memory_store.save_calls[0]["assistant_metadata"]["answer_status"] == "blocked"
    assert sensitive_service.calls == [
        {
            "scene": "query",
            "text": "Show me the internal roadmap",
            "team_id": 7,
        }
    ]


def test_kb_chat_stream_completes_with_blocked_payload_when_sensitive_query_matches():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore()
    service = KbChatService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        sensitive_word_service=FakeSensitiveWordService(blocked=True, matched_words=["secret"]),
    )
    request = SimpleNamespace(
        query="Tell me the secret launch plan",
        team_id=3,
        knowledge_base_id=9,
        category_id=4,
        session_id="session-1",
    )

    async def collect() -> list[str]:
        return [event async for event in service.stream(request, user_id=42)]

    events = asyncio.run(collect())
    payloads = _decode_sse_payloads(events)

    assert [payload["type"] for payload in payloads] == ["start", "complete"]
    assert payloads[-1]["data"]["answer_status"] == "blocked"
    assert payloads[-1]["data"]["retrieved_docs"] == []
    assert graph.last_state is None
    assert memory_store.save_calls[0]["assistant_metadata"]["answer_status"] == "blocked"


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
    assert state["allowed_document_statuses"] == list(VISIBLE_ASK_DOCUMENT_STATUSES)
    assert state["retrieval_version_mode"] == RETRIEVAL_VERSION_LIVE


def test_kb_chat_service_can_build_v2_initial_state():
    service = KbChatService(
        llm_factory=lambda: None,
        graph=FakeKbChatGraph(),
        memory_store=SimpleNamespace(),
        workflow_id="kb_chat_v2",
    )
    request = SimpleNamespace(
        query="How is Prescription Flow related to Payment?",
        knowledge_base_id=3,
        category_id=7,
        session_id="session-v2",
    )

    state = service.build_initial_state(request, user_id=99)

    assert state["metadata"]["workflow"] == "kb_chat_v2"
    assert state["workflow_id"] == "kb_chat_v2"
    assert state["question_type"] is None
    assert state["text_queries"] == []
    assert state["candidate_entities"] == []
    assert state["retrieval_evaluation"] == {}


def test_kb_chat_build_initial_state_keeps_assistant_context():
    service = KbChatService(
        llm_factory=lambda: None,
        graph=FakeKbChatGraph(),
        memory_store=FakeChatMemoryStore(),
    )
    request = SimpleNamespace(
        query="How should the assistant respond?",
        knowledge_base_id=3,
        category_id=7,
        assistant_id=5,
        assistant_name="Project Assistant",
        assistant_welcome_message="Hello",
        assistant_placeholder_text="Ask a setup question",
        assistant_llm_model_key="gpt-5-4-mini",
        assistant_persona_prompt="Be concise.",
        assistant_rule_template="Prefer step-by-step instructions.",
        assistant_suggested_prompts=["How do I get started?"],
        session_id="session-2",
    )

    state = service.build_initial_state(request, user_id=99)

    assert state["assistant_id"] == 5
    assert state["assistant_name"] == "Project Assistant"
    assert state["assistant_welcome_message"] == "Hello"
    assert state["assistant_placeholder_text"] == "Ask a setup question"
    assert state["assistant_llm_model_key"] == "gpt-5-4-mini"
    assert state["assistant_persona_prompt"] == "Be concise."
    assert state["assistant_rule_template"] == "Prefer step-by-step instructions."
    assert state["assistant_suggested_prompts"] == ["How do I get started?"]


def test_kb_chat_build_initial_state_allows_admin_preview_status_override():
    service = KbChatService(
        llm_factory=lambda: None,
        graph=FakeKbChatGraph(),
        memory_store=FakeChatMemoryStore(),
    )
    request = SimpleNamespace(
        query="Can I preview unpublished content?",
        knowledge_base_id=3,
        category_id=7,
        session_id="session-1",
        allowed_document_statuses=list(PREVIEW_ASK_DOCUMENT_STATUSES),
        retrieval_version_mode=RETRIEVAL_VERSION_CURRENT,
    )

    state = service.build_initial_state(request, user_id=99)

    assert state["allowed_document_statuses"] == [
        *PREVIEW_ASK_DOCUMENT_STATUSES,
    ]
    assert state["retrieval_version_mode"] == RETRIEVAL_VERSION_CURRENT


def test_kb_chat_preview_runs_without_persistence():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore()
    service = KbChatService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        sensitive_word_service=FakeSensitiveWordService(blocked=False),
    )
    request = SimpleNamespace(
        query="Preview this assistant",
        team_id=2,
        knowledge_base_id=9,
        category_id=4,
        assistant_name="Preview Assistant",
        assistant_welcome_message="Hello there",
        assistant_placeholder_text="Ask about setup",
        assistant_llm_model_key="qwen3-6-flash",
        assistant_persona_prompt="Be concise.",
        assistant_rule_template="Use bullets when needed.",
        assistant_suggested_prompts=["How do I start?"],
        allowed_document_statuses=list(PREVIEW_ASK_DOCUMENT_STATUSES),
        retrieval_version_mode=RETRIEVAL_VERSION_CURRENT,
    )

    response = asyncio.run(service.preview(request, user_id=42))

    assert response.answer == "LangGraph helps compose flows."
    assert response.assistant_name == "Preview Assistant"
    assert response.session_id is None
    assert response.log_id is None
    assert memory_store.load_calls == []
    assert memory_store.save_calls == []
    assert graph.last_state["assistant_welcome_message"] == "Hello there"
    assert graph.last_state["assistant_placeholder_text"] == "Ask about setup"
    assert graph.last_state["assistant_llm_model_key"] == "qwen3-6-flash"
    assert graph.last_state["assistant_persona_prompt"] == "Be concise."
    assert graph.last_state["assistant_suggested_prompts"] == ["How do I start?"]
    assert graph.last_state["allowed_document_statuses"] == [
        *PREVIEW_ASK_DOCUMENT_STATUSES,
    ]
    assert graph.last_state["retrieval_version_mode"] == RETRIEVAL_VERSION_CURRENT


def test_kb_chat_list_sessions_returns_history_for_user():
    memory_store = FakeChatMemoryStore()
    service = KbChatService(
        llm_factory=lambda: None, graph=FakeKbChatGraph(), memory_store=memory_store
    )

    sessions = asyncio.run(service.list_sessions(user_id=42, limit=10))

    assert len(sessions) == 1
    assert sessions[0].session_id == "session-1"
    assert sessions[0].knowledge_base_name == "Product Docs"
    assert sessions[0].assistant_name == "Project Assistant"
    assert memory_store.list_calls == [
        {
            "user_id": 42,
            "limit": 10,
            "project_app_id": None,
            "external_user_id": None,
        }
    ]


def test_kb_chat_get_session_returns_persisted_messages():
    memory_store = FakeChatMemoryStore()
    service = KbChatService(
        llm_factory=lambda: None, graph=FakeKbChatGraph(), memory_store=memory_store
    )

    session = asyncio.run(service.get_session(user_id=42, session_id="session-1"))

    assert session is not None
    assert session.session_id == "session-1"
    assert session.assistant_id == 5
    assert session.messages[0].role == "user"
    assert session.messages[1].content == "LangGraph helps compose flows."
    assert memory_store.detail_calls == [
        {
            "user_id": 42,
            "session_id": "session-1",
            "project_app_id": None,
            "external_user_id": None,
        }
    ]


def test_kb_chat_delete_session_removes_history_item():
    memory_store = FakeChatMemoryStore()
    service = KbChatService(
        llm_factory=lambda: None, graph=FakeKbChatGraph(), memory_store=memory_store
    )

    deleted = asyncio.run(service.delete_session(user_id=42, session_id="session-1"))

    assert deleted is True
    assert memory_store.delete_calls == [
        {
            "user_id": 42,
            "session_id": "session-1",
            "project_app_id": None,
            "external_user_id": None,
        }
    ]


def test_build_log_detail_response_serializes_nested_records():
    now = datetime.utcnow()
    record = KbChatLogDetailRecord(
        id=1,
        user_id=2,
        session_id="session-1",
        product_id=None,
        product_name=None,
        project_id=None,
        project_name=None,
        project_app_id=None,
        project_app_name=None,
        external_user_id=None,
        external_user_name=None,
        knowledge_base_id=9,
        knowledge_base_branch_ids=[],
        knowledge_base_name="Product Docs",
        assistant_id=5,
        assistant_name="Project Assistant",
        category_id=4,
        category_name="Guides",
        query="What is LangGraph?",
        answer_text="LangGraph helps compose flows.",
        answer_status="answered",
        retrieval_status="ok",
        retrieved_count=1,
        latency_ms=123,
        feedback_value=None,
        feedback_note=None,
        suggested_review_label="答案有依据但表达差",
        review_label="答案正确但不完整",
        review_note="答案漏掉了审批条件。",
        reviewed_at=now,
        reviewed_by_user_id=99,
        created_at=now,
        team_id=7,
        team_name="Support",
        retrieval_status_reason="Matched indexed content.",
        retrieval_queries=["what is langgraph"],
        retrieval_funnel={
            "mode": "hybrid",
            "query_count": 2,
            "rewritten_queries": [
                {"query": "what is langgraph", "chunk_count": 4},
                {"query": "langgraph basics", "chunk_count": 3},
            ],
            "stages": [
                {"key": "recalled_candidates", "label": "改写后总召回", "chunk_count": 7},
                {"key": "merged_candidates", "label": "融合去重后", "chunk_count": 5},
                {"key": "reranked_candidates", "label": "重排过滤后", "chunk_count": 2},
                {"key": "context_chunks", "label": "进入回答上下文", "chunk_count": 1},
            ],
        },
        answer_context="LangGraph is a stateful orchestration framework.",
        retrieved_docs=[
            KbChatDiagnosticDocRecord(
                rank=1,
                content="LangGraph is a stateful orchestration framework.",
                metadata={"document_title": "LangGraph Intro", "score": 0.9},
            )
        ],
        conversation_context=[
            KbChatDiagnosticMessageRecord(
                role="user",
                content="What is LangGraph?",
                created_at=now,
                is_current_turn=True,
            )
        ],
    )

    detail = _build_log_detail_response(record)

    assert detail.retrieved_docs[0].metadata["document_title"] == "LangGraph Intro"
    assert detail.retrieval_funnel is not None
    assert detail.retrieval_funnel.query_count == 2
    assert detail.retrieval_funnel.stages[0].chunk_count == 7
    assert detail.retrieval_funnel.stages[1].chunk_count == 5
    assert detail.suggested_review_label == "答案有依据但表达差"
    assert detail.review_label == "答案正确但不完整"
    assert detail.conversation_context[0].role == "user"
