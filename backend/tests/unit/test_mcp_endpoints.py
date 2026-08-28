from types import SimpleNamespace

from app.api.dependencies.embed import require_enterprise_service_token
from app.api.dependencies.mcp_auth import get_mcp_auth_context
from app.db.session import get_db
from app.main import app


def test_mcp_bootstrap_endpoint_returns_bootstrap_payload(client, monkeypatch):
    async def _fake_require_enterprise_service_token():
        return None

    async def _fake_get_db():
        yield object()

    async def _fake_bootstrap(self, *, request):
        assert request.product_code == "test"
        return {
            "access_token": "mcp-token",
            "token_type": "bearer",
            "expires_in_seconds": 1800,
            "scope": {
                "product_code": "test",
                "project_code": "test",
                "app_code": "test",
            },
        }

    monkeypatch.setattr("app.api.v1.endpoints.mcp.McpService.bootstrap", _fake_bootstrap)
    app.dependency_overrides[require_enterprise_service_token] = _fake_require_enterprise_service_token
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.post(
            "/api/v1/mcp/bootstrap",
            json={
                "product_code": "test",
                "project_code": "test",
                "app_code": "test",
                "client_user_id": "zhangsan",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "mcp-token"
    assert data["scope"]["project_code"] == "test"


def test_mcp_bootstrap_endpoint_allows_missing_optional_client_fields(client, monkeypatch):
    async def _fake_require_enterprise_service_token():
        return None

    async def _fake_get_db():
        yield object()

    async def _fake_bootstrap(self, *, request):
        assert request.client_user_id is None
        assert request.client_user_name is None
        assert request.client_host is None
        return {
            "access_token": "mcp-token",
            "token_type": "bearer",
            "expires_in_seconds": 1800,
            "scope": {
                "product_code": "test",
                "project_code": "test",
                "app_code": "test",
            },
        }

    monkeypatch.setattr("app.api.v1.endpoints.mcp.McpService.bootstrap", _fake_bootstrap)
    app.dependency_overrides[require_enterprise_service_token] = _fake_require_enterprise_service_token
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.post(
            "/api/v1/mcp/bootstrap",
            json={
                "product_code": "test",
                "project_code": "test",
                "app_code": "test",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["access_token"] == "mcp-token"


def test_mcp_bootstrap_endpoint_rejects_invalid_service_token(client):
    response = client.post(
        "/api/v1/mcp/bootstrap",
        headers={"Authorization": "Bearer wrong-token"},
        json={
            "product_code": "test",
            "project_code": "test",
            "app_code": "test",
            "client_user_id": "zhangsan",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid enterprise service token"


def test_mcp_scope_resolve_endpoint_supports_mcp_auth_context(client, monkeypatch):
    async def _fake_get_db():
        yield object()

    async def _fake_get_mcp_auth_context():
        return SimpleNamespace(user=None, mcp_token=SimpleNamespace(project_app_id=2))

    async def _fake_resolve_scope(self, *, product_code: str, project_code: str, app_code: str):
        assert product_code == "test"
        return {
            "team_id": 1,
            "product_id": 2,
            "product_code": "test",
            "product_name": "B2C",
            "project_id": 3,
            "project_code": "test",
            "project_name": "Retail",
            "project_app_id": 4,
            "app_code": "test",
            "app_name": "Mini Program",
            "assistant_id": 5,
            "assistant_name": "Assistant",
            "knowledge_base_ids": [18],
            "knowledge_base_branch_ids": [],
            "bindings": [
                {
                    "knowledge_base_id": 18,
                    "knowledge_base_name": "Retail KB",
                    "knowledge_base_branch_id": None,
                    "knowledge_base_branch_name": None,
                }
            ],
        }

    monkeypatch.setattr("app.api.v1.endpoints.mcp.McpService.resolve_scope", _fake_resolve_scope)
    app.dependency_overrides[get_mcp_auth_context] = _fake_get_mcp_auth_context
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.post(
            "/api/v1/mcp/scope/resolve",
            json={
                "product_code": "test",
                "project_code": "test",
                "app_code": "test",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["product_code"] == "test"
    assert data["knowledge_base_ids"] == [18]
