from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.application.mcp_service as mcp_service_module
from app.application.mcp_service import McpService
from app.repositories.project_repository import ProjectAppBindingRecord


@dataclass
class _FakeProduct:
    id: int
    code: str
    name: str


@dataclass
class _FakeProject:
    id: int
    team_id: int
    code: str
    name: str


@dataclass
class _FakeApp:
    id: int
    code: str
    name: str


@dataclass
class _FakeAssistant:
    id: int
    name: str


@dataclass
class _FakeRuntime:
    product: _FakeProduct
    project: _FakeProject
    app: _FakeApp
    assistant: _FakeAssistant | None
    bindings: list[ProjectAppBindingRecord]


@dataclass
class _FakeKbResponse:
    answer: str
    answer_status: str
    retrieved_docs: list[dict]


class _FakeProjectRepository:
    def __init__(self, runtime: _FakeRuntime | None) -> None:
        self.runtime = runtime
        self.calls: list[dict[str, object]] = []

    @staticmethod
    def normalize_code(code: str) -> str:
        return (code or "").strip().lower()

    async def get_runtime_by_codes(
        self,
        *,
        product_code: str,
        project_code: str,
        app_code: str,
        active_only: bool = True,
    ):
        self.calls.append(
            {
                "product_code": product_code,
                "project_code": project_code,
                "app_code": app_code,
                "active_only": active_only,
            }
        )
        return self.runtime

    async def get_runtime_by_app_id(
        self,
        *,
        project_app_id: int,
        active_only: bool = True,
    ):
        self.calls.append(
            {
                "project_app_id": project_app_id,
                "active_only": active_only,
            }
        )
        return self.runtime


class _FakeTeamRepository:
    def __init__(self, can_access: bool) -> None:
        self.can_access = can_access
        self.calls: list[int] = []

    async def can_access_team(self, team_id: int) -> bool:
        self.calls.append(team_id)
        return self.can_access


def _build_service(
    *,
    runtime: _FakeRuntime | None,
    can_access_team: bool,
) -> McpService:
    service = McpService.__new__(McpService)
    service.db = object()
    service.auth_context = SimpleNamespace(user=SimpleNamespace(id=42), mcp_token=None)
    service.project_repository = _FakeProjectRepository(runtime)
    service.team_repository = _FakeTeamRepository(can_access_team)
    return service


@pytest.mark.asyncio
async def test_mcp_service_resolve_scope_returns_bound_runtime_scope():
    service = _build_service(
    runtime=_FakeRuntime(
            product=_FakeProduct(id=1, code="crm", name="CRM"),
            project=_FakeProject(id=2, team_id=3, code="console", name="Console"),
            app=_FakeApp(id=4, code="web", name="Web"),
            assistant=_FakeAssistant(id=5, name="Project Assistant"),
            bindings=[
                ProjectAppBindingRecord(
                    knowledge_base_id=10,
                    knowledge_base_name="CRM KB",
                ),
                ProjectAppBindingRecord(
                    knowledge_base_id=11,
                    knowledge_base_name="Billing KB",
                ),
            ],
        ),
        can_access_team=True,
    )

    result = await service.resolve_scope(
        product_code="crm",
        project_code="console",
        app_code="web",
    )

    assert result.team_id == 3
    assert result.product_id == 1
    assert result.project_id == 2
    assert result.project_app_id == 4
    assert result.assistant_id == 5
    assert result.knowledge_base_ids == [10, 11]
    assert result.knowledge_base_branch_ids == []
    assert result.bindings[0].knowledge_base_name == "CRM KB"
    assert service.project_repository.calls == [
        {
            "product_code": "crm",
            "project_code": "console",
            "app_code": "web",
            "active_only": True,
        }
    ]
    assert service.team_repository.calls == [3]


@pytest.mark.asyncio
async def test_mcp_service_resolve_scope_rejects_team_without_access():
    service = _build_service(
        runtime=_FakeRuntime(
            product=_FakeProduct(id=1, code="crm", name="CRM"),
            project=_FakeProject(id=2, team_id=3, code="console", name="Console"),
            app=_FakeApp(id=4, code="web", name="Web"),
            assistant=_FakeAssistant(id=5, name="Project Assistant"),
            bindings=[],
        ),
        can_access_team=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.resolve_scope(
            product_code="crm",
            project_code="console",
            app_code="web",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Team access denied"


@pytest.mark.asyncio
async def test_mcp_service_resolve_scope_returns_404_when_runtime_missing():
    service = _build_service(runtime=None, can_access_team=True)

    with pytest.raises(HTTPException) as exc_info:
        await service.resolve_scope(
            product_code="crm",
            project_code="console",
            app_code="web",
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Active project application not found"


@pytest.mark.asyncio
async def test_mcp_service_search_returns_mapped_retrieval_items(monkeypatch: pytest.MonkeyPatch):
    service = _build_service(
        runtime=_FakeRuntime(
            product=_FakeProduct(id=1, code="crm", name="CRM"),
            project=_FakeProject(id=2, team_id=3, code="console", name="Console"),
            app=_FakeApp(id=4, code="web", name="Web"),
            assistant=_FakeAssistant(id=5, name="Project Assistant"),
            bindings=[
                ProjectAppBindingRecord(
                    knowledge_base_id=10,
                    knowledge_base_name="CRM KB",
                ),
            ],
        ),
        can_access_team=True,
    )

    captured: dict[str, object] = {}

    async def _fake_retrieval(**kwargs):
        captured.update(kwargs)
        return {
            "retrieved_docs": [
                {
                    "content": "Use /api/v1/ask/stream for SSE.",
                    "metadata": {
                        "document_id": 101,
                        "document_title": "Frontend SSE Guide",
                        "section_path": "frontend/sse",
                        "score": 0.12,
                        "rerank_score": 0.91,
                    },
                }
            ]
        }

    monkeypatch.setattr(mcp_service_module, "run_multi_query_kb_text_retrieval", _fake_retrieval)

    result = await service.search(
        request=mcp_service_module.McpSearchRequest(
            query="How do I handle SSE?",
            product_code="crm",
            project_code="console",
            app_code="web",
            top_k=5,
        )
    )

    assert captured["knowledge_base_id"] == 10
    assert captured["team_id"] == 3
    assert captured["result_limit"] == 5
    assert result.items[0].document_id == 101
    assert result.items[0].document_title == "Frontend SSE Guide"
    assert result.items[0].section_path == "frontend/sse"
    assert result.items[0].rerank_score == 0.91


@pytest.mark.asyncio
async def test_mcp_service_search_rejects_multi_knowledge_base_scope():
    service = _build_service(
        runtime=_FakeRuntime(
            product=_FakeProduct(id=1, code="crm", name="CRM"),
            project=_FakeProject(id=2, team_id=3, code="console", name="Console"),
            app=_FakeApp(id=4, code="web", name="Web"),
            assistant=_FakeAssistant(id=5, name="Project Assistant"),
            bindings=[
                ProjectAppBindingRecord(
                    knowledge_base_id=10,
                    knowledge_base_name="CRM KB",
                ),
                ProjectAppBindingRecord(
                    knowledge_base_id=11,
                    knowledge_base_name="Billing KB",
                ),
            ],
        ),
        can_access_team=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.search(
            request=mcp_service_module.McpSearchRequest(
                query="How do I handle SSE?",
                product_code="crm",
                project_code="console",
                app_code="web",
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "MCP search currently supports exactly one bound knowledge base"


@pytest.mark.asyncio
async def test_mcp_service_answer_uses_stateless_preview_response(
    monkeypatch: pytest.MonkeyPatch,
):
    service = _build_service(
        runtime=_FakeRuntime(
            product=_FakeProduct(id=1, code="crm", name="CRM"),
            project=_FakeProject(id=2, team_id=3, code="console", name="Console"),
            app=_FakeApp(id=4, code="web", name="Web"),
            assistant=_FakeAssistant(id=5, name="Project Assistant"),
            bindings=[
                ProjectAppBindingRecord(
                    knowledge_base_id=10,
                    knowledge_base_name="CRM KB",
                ),
            ],
        ),
        can_access_team=True,
    )

    captured: dict[str, object] = {}

    class _FakeKbChatService:
        async def preview(self, request, *, user_id: int):
            captured["method"] = "preview"
            captured["user_id"] = user_id
            captured["knowledge_base_id"] = request.knowledge_base_id
            captured["project_app_id"] = request.project_app_id
            captured["query"] = request.query
            captured["session_id"] = request.session_id
            return _FakeKbResponse(
                answer="Use the stream endpoint.",
                answer_status="answered",
                retrieved_docs=[{"content": "doc"}],
            )

    monkeypatch.setattr(
        mcp_service_module,
        "get_kb_chat_service",
        lambda: _FakeKbChatService(),
    )

    result = await service.answer(
        request=mcp_service_module.McpAnswerRequest(
            query="How do I handle SSE?",
            product_code="crm",
            project_code="console",
            app_code="web",
        )
    )

    assert captured == {
        "method": "preview",
        "user_id": 42,
        "knowledge_base_id": 10,
        "project_app_id": 4,
        "query": "How do I handle SSE?",
        "session_id": None,
    }
    assert result.answer == "Use the stream endpoint."
    assert result.answer_status == "answered"
    assert result.retrieved_docs == [{"content": "doc"}]


@pytest.mark.asyncio
async def test_mcp_service_answer_rejects_multi_knowledge_base_scope():
    service = _build_service(
        runtime=_FakeRuntime(
            product=_FakeProduct(id=1, code="crm", name="CRM"),
            project=_FakeProject(id=2, team_id=3, code="console", name="Console"),
            app=_FakeApp(id=4, code="web", name="Web"),
            assistant=_FakeAssistant(id=5, name="Project Assistant"),
            bindings=[
                ProjectAppBindingRecord(
                    knowledge_base_id=10,
                    knowledge_base_name="CRM KB",
                ),
                ProjectAppBindingRecord(
                    knowledge_base_id=11,
                    knowledge_base_name="Billing KB",
                ),
            ],
        ),
        can_access_team=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.answer(
            request=mcp_service_module.McpAnswerRequest(
                query="How do I handle SSE?",
                product_code="crm",
                project_code="console",
                app_code="web",
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "MCP answer currently supports exactly one bound knowledge base"


@pytest.mark.asyncio
async def test_mcp_service_bootstrap_returns_short_lived_token(monkeypatch: pytest.MonkeyPatch):
    service = _build_service(
        runtime=_FakeRuntime(
            product=_FakeProduct(id=1, code="test", name="B2C"),
            project=_FakeProject(id=2, team_id=3, code="test", name="Retail"),
            app=_FakeApp(id=4, code="test", name="Mini Program"),
            assistant=_FakeAssistant(id=5, name="Project Assistant"),
            bindings=[
                ProjectAppBindingRecord(
                    knowledge_base_id=10,
                    knowledge_base_name="Retail KB",
                ),
            ],
        ),
        can_access_team=True,
    )

    captured: dict[str, object] = {}

    def _fake_create_mcp_token(**kwargs):
        captured.update(kwargs)
        return "bootstrap-token"

    monkeypatch.setattr(mcp_service_module, "create_mcp_token", _fake_create_mcp_token)

    result = await service.bootstrap(
        request=mcp_service_module.McpBootstrapRequest(
            product_code="test",
            project_code="test",
            app_code="test",
            client_user_id="zhangsan",
            client_user_name="张三",
            client_editor="trae",
            client_host="DESKTOP-001",
        )
    )

    assert result.access_token == "bootstrap-token"
    assert result.token_type == "bearer"
    assert result.scope.product_code == "test"
    assert captured["project_app_id"] == 4
    assert captured["client_user_id"] == "zhangsan"


@pytest.mark.asyncio
async def test_mcp_service_bootstrap_allows_missing_optional_client_fields(
    monkeypatch: pytest.MonkeyPatch,
):
    service = _build_service(
        runtime=_FakeRuntime(
            product=_FakeProduct(id=1, code="test", name="B2C"),
            project=_FakeProject(id=2, team_id=3, code="test", name="Retail"),
            app=_FakeApp(id=4, code="test", name="Mini Program"),
            assistant=_FakeAssistant(id=5, name="Project Assistant"),
            bindings=[
                ProjectAppBindingRecord(
                    knowledge_base_id=10,
                    knowledge_base_name="Retail KB",
                ),
            ],
        ),
        can_access_team=True,
    )

    captured: dict[str, object] = {}

    def _fake_create_mcp_token(**kwargs):
        captured.update(kwargs)
        return "bootstrap-token"

    monkeypatch.setattr(mcp_service_module, "create_mcp_token", _fake_create_mcp_token)

    result = await service.bootstrap(
        request=mcp_service_module.McpBootstrapRequest(
            product_code="test",
            project_code="test",
            app_code="test",
        )
    )

    assert result.access_token == "bootstrap-token"
    assert captured["client_user_id"] == "unknown-user"
    assert captured["client_user_name"] is None
    assert captured["client_host"] is None


@pytest.mark.asyncio
async def test_mcp_service_resolve_scope_uses_bound_mcp_token_context():
    service = McpService.__new__(McpService)
    service.db = object()
    service.auth_context = SimpleNamespace(
        user=None,
        mcp_token=SimpleNamespace(
            product_id=1,
            project_id=2,
            project_app_id=4,
            product_code="test",
            project_code="test",
            app_code="test",
            client_user_id="zhangsan",
            client_user_name="张三",
            client_editor="trae",
            client_host="DESKTOP-001",
        ),
    )
    service.project_repository = _FakeProjectRepository(
        _FakeRuntime(
            product=_FakeProduct(id=1, code="test", name="B2C"),
            project=_FakeProject(id=2, team_id=3, code="test", name="Retail"),
            app=_FakeApp(id=4, code="test", name="Mini Program"),
            assistant=_FakeAssistant(id=5, name="Project Assistant"),
            bindings=[
                ProjectAppBindingRecord(
                    knowledge_base_id=10,
                    knowledge_base_name="Retail KB",
                ),
            ],
        )
    )
    service.team_repository = _FakeTeamRepository(can_access=True)

    result = await service.resolve_scope(
        product_code="test",
        project_code="test",
        app_code="test",
    )

    assert result.project_app_id == 4
    assert service.project_repository.calls == [
        {
            "project_app_id": 4,
            "active_only": True,
        }
    ]


@pytest.mark.asyncio
async def test_mcp_service_rejects_scope_mismatch_for_mcp_token():
    service = McpService.__new__(McpService)
    service.db = object()
    service.auth_context = SimpleNamespace(
        user=None,
        mcp_token=SimpleNamespace(
            product_id=1,
            project_id=2,
            project_app_id=4,
            product_code="test",
            project_code="test",
            app_code="test",
            client_user_id="zhangsan",
            client_user_name="张三",
            client_editor="trae",
            client_host="DESKTOP-001",
        ),
    )
    service.project_repository = _FakeProjectRepository(None)
    service.team_repository = _FakeTeamRepository(can_access=True)

    with pytest.raises(HTTPException) as exc_info:
        await service.resolve_scope(
            product_code="other",
            project_code="test",
            app_code="test",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "MCP token scope mismatch"
