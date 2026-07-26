import asyncio
import json
from datetime import datetime

from app.api.v1.endpoints.qa_review import _build_log_detail_response
from app.application.agent.conversation_service import AgentConversationService
from app.application.agent.input_builder import AgentRunRequest
from app.application.agent.run_service import AgentRunService
from app.repositories.kb_chat_log_repository import (
    KbChatDiagnosticMessageRecord,
    KbChatLogDetailRecord,
)
from app.services.chat_memory import (
    ChatMemoryContext,
    ChatSessionDetailRecord,
    ChatSessionSummaryRecord,
)
from app.services.content_risk_detection_service import (
    ContentRiskDetectionResult,
    ContentRiskRuleHit,
)
from app.services.document_lifecycle import (
    PREVIEW_ASK_DOCUMENT_STATUSES,
    VISIBLE_ASK_DOCUMENT_STATUSES,
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
            "response": {
                "answer": "LangGraph helps compose flows.",
                "status": "answered",
                "sources": [
                    {
                        "content": "LangGraph is a stateful orchestration framework.",
                        "metadata": {
                            "document_id": 11,
                            "chunk_index": 0,
                            "document_title": "LangGraph Intro",
                        },
                    }
                ],
            },
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
            "semantic_queries": ["What is LangGraph?", "LangGraph basics"],
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
            "type": "custom",
            "data": {
                "type": "node_complete",
                "workflow_id": "knowledge_qa",
                "node_id": "retrieve_knowledge",
                "node_state": {
                    "retrieval_result": {
                        "evidence_items": [
                            {
                                "ref_id": "ref-1",
                                "role": "primary",
                                "kind": "text_chunk",
                                "content": "LangGraph is a stateful orchestration framework.",
                                "source": {
                                    "document_id": 11,
                                    "chunk_index": 0,
                                    "document_title": "LangGraph Intro",
                                },
                            }
                        ]
                    },
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
                    "semantic_queries": ["What is LangGraph?", "LangGraph basics"],
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
                },
            },
        }
        yield {
            "type": "custom",
            "data": {"workflow_id": "agent", "node_id": "respond", "text": "LangGraph "},
        }
        yield {
            "type": "custom",
            "data": {"workflow_id": "agent", "node_id": "respond", "text": "helps "},
        }
        yield {
            "type": "custom",
            "data": {
                "workflow_id": "agent",
                "node_id": "respond",
                "text": "compose flows.",
            },
        }
        yield {
            "type": "updates",
            "data": {
                "respond": {
                    "response": {
                        "answer": "LangGraph helps compose flows.",
                        "status": "answered",
                        "sources": [
                            {
                                "content": "LangGraph is a stateful orchestration framework.",
                                "metadata": {
                                    "document_id": 11,
                                    "chunk_index": 0,
                                    "document_title": "LangGraph Intro",
                                },
                            }
                        ],
                    },
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
        assistant_id: int | None,
        category_id: int | None,
        user_message: str,
        answer_message: str,
        answer_metadata: dict | None = None,
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
                "assistant_id": assistant_id,
                "category_id": category_id,
                "user_message": user_message,
                "answer_message": answer_message,
                "answer_metadata": answer_metadata,
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


class FakeContentRiskDetectionService:
    def __init__(self, blocked: bool = False, matched_rules: list[str] | None = None) -> None:
        self.blocked = blocked
        self.matched_rules = matched_rules or ["secret"]
        self.calls = []

    async def check_text(self, *, scene: str, text: str):
        self.calls.append({"scene": scene, "text": text})
        hits = [
            ContentRiskRuleHit(
                rule_id=index + 1,
                library_id=1,
                rule_name=rule_name,
                risk_category="测试分类",
                risk_level="high",
                action="block",
                match_mode="contains",
                pattern=rule_name,
                matched_text=rule_name,
            )
            for index, rule_name in enumerate(self.matched_rules)
        ] if self.blocked else []
        return ContentRiskDetectionResult(
            scene=scene,
            action="block" if self.blocked else "pass",
            blocked=self.blocked,
            risk_level="high" if self.blocked else None,
            hits=hits,
            elapsed_ms=1,
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
    service = AgentRunService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        content_risk_detection_service=FakeContentRiskDetectionService(blocked=False),
    )
    request = AgentRunRequest(
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
    conversation = graph.last_state["input"]["conversation"]
    assert conversation["history"][0]["role"] == "user"
    assert conversation["summary"] == "The user is asking about LangGraph basics."
    assert memory_store.load_calls == [
        {
            "user_id": 42,
            "session_id": "session-1",
            "project_app_id": None,
            "external_user_id": None,
        }
    ]
    assert memory_store.save_calls[0]["answer_message"] == "LangGraph helps compose flows."
    assert memory_store.save_calls[0]["answer_metadata"]["semantic_queries"] == [
        "What is LangGraph?",
        "LangGraph basics",
    ]


def test_kb_chat_stream_emits_standardized_envelopes():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore()
    service = AgentRunService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        content_risk_detection_service=FakeContentRiskDetectionService(blocked=False),
    )
    request = AgentRunRequest(
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
    assert payloads[3]["data"] == {}
    assert payloads[8]["data"] == {}
    assert payloads[-1]["data"]["answer"] == "LangGraph helps compose flows."
    assert payloads[-1]["data"]["answer_status"] == "answered"
    assert payloads[-1]["data"]["session_id"]
    assert memory_store.load_calls[0]["session_id"] == payloads[-1]["data"]["session_id"]
    assert memory_store.save_calls[0]["answer_message"] == "LangGraph helps compose flows."
    assert memory_store.save_calls[0]["answer_metadata"]["semantic_queries"] == []
    assert (
        graph.last_state["input"]["conversation"]["session_id"]
        == payloads[-1]["data"]["session_id"]
    )


def test_kb_chat_invoke_blocks_sensitive_query_before_graph_runs():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore()
    risk_service = FakeContentRiskDetectionService(blocked=True, matched_rules=["internal roadmap"])
    service = AgentRunService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        content_risk_detection_service=risk_service,
    )
    request = AgentRunRequest(
        query="Show me the internal roadmap",
        team_id=7,
        knowledge_base_id=9,
        category_id=4,
        session_id="session-1",
    )

    response = asyncio.run(service.invoke(request, user_id=42))

    assert response.answer_status == "blocked"
    assert "internal roadmap" in response.answer_text
    assert response.retrieved_docs == []
    assert graph.last_state is None
    assert memory_store.save_calls[0]["answer_metadata"]["answer_status"] == "blocked"
    assert risk_service.calls == [
        {
            "scene": "query",
            "text": "Show me the internal roadmap",
        }
    ]


def test_kb_chat_stream_completes_with_blocked_payload_when_sensitive_query_matches():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore()
    service = AgentRunService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        content_risk_detection_service=FakeContentRiskDetectionService(blocked=True, matched_rules=["secret"]),
    )
    request = AgentRunRequest(
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
    assert memory_store.save_calls[0]["answer_metadata"]["answer_status"] == "blocked"


def test_kb_chat_build_initial_state_keeps_category_id():
    service = AgentRunService(
        llm_factory=lambda: None,
        graph=FakeKbChatGraph(),
        memory_store=FakeChatMemoryStore(),
    )
    request = AgentRunRequest(
        query="What is the refund policy?",
        knowledge_base_id=3,
        category_id=7,
        session_id="session-1",
    )

    state = service.build_initial_state(request, user_id=99)

    agent_input = state["input"]
    assert agent_input["resources"]["knowledge_base_id"] == 3
    assert agent_input["resources"]["category_id"] == 7
    assert agent_input["query"] == "What is the refund policy?"
    assert agent_input["conversation"]["session_id"] == "session-1"
    assert agent_input["conversation"]["history"] == []
    assert agent_input["resources"]["allowed_document_statuses"] == list(
        VISIBLE_ASK_DOCUMENT_STATUSES
    )


def test_kb_chat_build_initial_state_keeps_assistant_context():
    service = AgentRunService(
        llm_factory=lambda: None,
        graph=FakeKbChatGraph(),
        memory_store=FakeChatMemoryStore(),
    )
    request = AgentRunRequest(
        query="How should the assistant respond?",
        knowledge_base_id=3,
        category_id=7,
        assistant_id=5,
        assistant_name="Project Assistant",
        assistant_llm_model_key="gpt-5-4-mini",
        assistant_persona_prompt="Be concise.",
        assistant_rule_template="Prefer step-by-step instructions.",
        session_id="session-2",
    )

    state = service.build_initial_state(request, user_id=99)

    assistant = state["input"]["assistant"]
    assert assistant["id"] == 5
    assert assistant["name"] == "Project Assistant"
    assert assistant["model_key"] == "gpt-5-4-mini"
    assert assistant["persona_prompt"] == "Be concise."
    assert assistant["rule_template"] == "Prefer step-by-step instructions."


def test_kb_chat_build_initial_state_allows_admin_preview_status_override():
    service = AgentRunService(
        llm_factory=lambda: None,
        graph=FakeKbChatGraph(),
        memory_store=FakeChatMemoryStore(),
    )
    request = AgentRunRequest(
        query="Can I preview unpublished content?",
        knowledge_base_id=3,
        category_id=7,
        session_id="session-1",
        allowed_document_statuses=list(PREVIEW_ASK_DOCUMENT_STATUSES),
    )

    state = service.build_initial_state(request, user_id=99)

    assert state["input"]["resources"]["allowed_document_statuses"] == [
        *PREVIEW_ASK_DOCUMENT_STATUSES,
    ]


def test_kb_chat_preview_runs_without_persistence():
    graph = FakeKbChatGraph()
    memory_store = FakeChatMemoryStore()
    service = AgentRunService(
        llm_factory=lambda: None,
        graph=graph,
        memory_store=memory_store,
        content_risk_detection_service=FakeContentRiskDetectionService(blocked=False),
    )
    request = AgentRunRequest(
        query="Preview this assistant",
        team_id=2,
        knowledge_base_id=9,
        category_id=4,
        assistant_name="Preview Assistant",
        assistant_llm_model_key="qwen3-6-flash",
        assistant_persona_prompt="Be concise.",
        assistant_rule_template="Use bullets when needed.",
        allowed_document_statuses=list(PREVIEW_ASK_DOCUMENT_STATUSES),
    )

    response = asyncio.run(service.preview(request, user_id=42))

    assert response.answer == "LangGraph helps compose flows."
    assert response.assistant_name == "Preview Assistant"
    assert response.session_id is None
    assert response.log_id is None
    assert memory_store.load_calls == []
    assert memory_store.save_calls == []
    agent_input = graph.last_state["input"]
    assert agent_input["assistant"]["model_key"] == "qwen3-6-flash"
    assert agent_input["assistant"]["persona_prompt"] == "Be concise."
    assert agent_input["resources"]["allowed_document_statuses"] == [
        *PREVIEW_ASK_DOCUMENT_STATUSES,
    ]


def test_kb_chat_list_sessions_returns_history_for_user():
    memory_store = FakeChatMemoryStore()
    service = AgentConversationService(memory_store=memory_store)

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
    service = AgentConversationService(memory_store=memory_store)

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
    service = AgentConversationService(memory_store=memory_store)

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
        knowledge_base_name="Product Docs",
        assistant_id=5,
        assistant_name="Project Assistant",
        category_id=4,
        category_name="Guides",
        query="What is LangGraph?",
        answer_text="LangGraph helps compose flows.",
        answer_status="answered",
        retrieval_status="ok",
        latency_ms=123,
        text_hit_count=1,
        graph_hit_count=0,
        merged_candidate_count=1,
        final_context_count=1,
        empty_reason=None,
        rerank_enabled=True,
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
        trace_payload={
            "retrieval": {
                "queries": ["what is langgraph"],
                "funnel": {
                    "mode": "hybrid",
                    "query_count": 2,
                    "stages": [
                        {
                            "key": "recalled_candidates",
                            "label": "改写后总召回",
                            "chunk_count": 7,
                        }
                    ],
                },
            }
        },
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

    assert detail.trace_payload is not None
    assert detail.trace_payload["retrieval"]["funnel"]["query_count"] == 2
    assert detail.trace_payload["retrieval"]["funnel"]["stages"][0]["chunk_count"] == 7
    assert detail.suggested_review_label == "答案有依据但表达差"
    assert detail.review_label == "答案正确但不完整"
    assert detail.conversation_context[0].role == "user"
