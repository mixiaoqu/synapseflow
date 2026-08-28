from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from jose import jwt
from pydantic import ValidationError

from app.api.dependencies.widget import validate_widget_access
from app.application.integration_bootstrap_service import IntegrationBootstrapService
from app.application.project_app_access_service import ProjectAppAccessService
from app.core.config import settings
from app.core.security import (
    create_embed_token,
    create_widget_token,
    decode_embed_token,
    decode_widget_token,
)
from app.models.schemas.widget import (
    IntegrationBootstrapCreate,
    IntegrationPrincipal,
    WidgetPageContext,
)


class _FakeCredentialRepository:
    def __init__(self):
        self.credential = None

    async def get_project_app(self, *, project_id: int, app_id: int):
        if project_id != 20 or app_id != 30:
            return None
        return SimpleNamespace(id=30, project_id=20)

    async def get_access_credential_by_app(self, project_app_id: int):
        if self.credential and self.credential.project_app_id == project_app_id:
            return self.credential
        return None

    async def get_project_app_team_id(self, *, project_id: int, app_id: int):
        return 1 if project_id == 20 and app_id == 30 else None

    async def get_access_credential_by_client_id(self, client_id: str):
        if self.credential and self.credential.client_id == client_id:
            return self.credential
        return None

    async def save_access_credential(self, credential):
        self.credential = credential
        return credential


def _build_service(repository: _FakeCredentialRepository) -> ProjectAppAccessService:
    service = ProjectAppAccessService.__new__(ProjectAppAccessService)
    service.repository = repository
    service.secret_pepper = "unit-test-pepper"
    service.user = SimpleNamespace(id=7, role="operator")
    service.permission_service = SimpleNamespace(
        has_team_permission=lambda user, team_id, permission: None
    )

    async def _allow_permission(user, team_id, permission):
        return user.id == 7 and team_id == 1

    service.permission_service.has_team_permission = _allow_permission
    return service


@pytest.mark.asyncio
async def test_create_access_rejects_user_without_project_team_permission():
    repository = _FakeCredentialRepository()
    service = _build_service(repository)

    async def _deny_permission(user, team_id, permission):
        return False

    service.permission_service.has_team_permission = _deny_permission

    with pytest.raises(HTTPException) as exc_info:
        await service.create_access(
            project_id=20,
            app_id=30,
            allowed_origins=["https://admin.example.com"],
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_create_access_generates_scoped_client_credentials():
    repository = _FakeCredentialRepository()
    service = _build_service(repository)

    result = await service.create_access(
        project_id=20,
        app_id=30,
        allowed_origins=["https://admin.example.com"],
    )

    assert result.client_id.startswith("sfc_")
    assert result.client_secret.startswith("sfs_")
    assert result.credential.project_app_id == 30
    assert result.credential.client_secret_digest != result.client_secret
    assert service.verify_client_secret(result.credential, result.client_secret) is True
    assert service.verify_client_secret(result.credential, "sfs_wrong") is False


@pytest.mark.asyncio
async def test_reset_secret_invalidates_previous_secret_and_widget_tokens():
    repository = _FakeCredentialRepository()
    service = _build_service(repository)
    created = await service.create_access(
        project_id=20,
        app_id=30,
        allowed_origins=["https://admin.example.com"],
    )

    reset = await service.reset_secret(project_id=20, app_id=30)

    assert reset.client_secret != created.client_secret
    assert reset.credential.client_id == created.credential.client_id
    assert reset.credential.token_version == 2
    assert service.verify_client_secret(reset.credential, created.client_secret) is False
    assert service.verify_client_secret(reset.credential, reset.client_secret) is True


def test_widget_token_roundtrip_preserves_platform_and_trusted_context():
    token = create_widget_token(
        client_id="sfc_client",
        team_id=1,
        product_id=10,
        project_id=20,
        project_app_id=30,
        external_user_id="user-1",
        external_user_name="张三",
        trusted_scope={"store_id": "store-1", "warehouse_id": "warehouse-2"},
        initial_page_type="order-detail",
        token_version=3,
    )

    payload = decode_widget_token(token)

    assert payload["team_id"] == 1
    assert payload["sub"] == "sfc_client:user-1"
    assert payload["client_id"] == "sfc_client"
    assert payload["product_id"] == 10
    assert payload["project_id"] == 20
    assert payload["project_app_id"] == 30
    assert payload["trusted_scope"] == {
        "store_id": "store-1",
        "warehouse_id": "warehouse-2",
    }
    assert payload["token_version"] == 3


def test_existing_embed_token_contract_remains_valid():
    token = create_embed_token(
        project_id=20,
        project_app_id=30,
        external_user_id="user-1",
        store_id="store-1",
    )

    payload = decode_embed_token(token)

    assert payload["project_id"] == 20
    assert payload["project_app_id"] == 30


def test_widget_token_rejects_missing_platform_fields():
    token = jwt.encode(
        {
            "sub": "user-1",
            "type": "widget",
            "project_id": 20,
            "project_app_id": 30,
            "external_user_id": "user-1",
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(ValueError, match="Invalid widget token"):
        decode_widget_token(token)


@pytest.mark.asyncio
async def test_integration_bootstrap_resolves_platform_scope_from_client_id(monkeypatch):
    credential = SimpleNamespace(
        project_app_id=30,
        client_id="sfc_client",
        client_secret_digest="digest",
        enabled=True,
        token_version=4,
    )
    runtime = SimpleNamespace(
        product=SimpleNamespace(id=10),
        project=SimpleNamespace(id=20, team_id=1),
        app=SimpleNamespace(id=30, widget_version="1.0.0", name="采购助手"),
    )
    service = IntegrationBootstrapService.__new__(IntegrationBootstrapService)
    service.access_repository = SimpleNamespace(
        get_access_credential_by_client_id=lambda client_id: None
    )

    async def _get_credential(client_id):
        assert client_id == "sfc_client"
        return credential

    async def _get_runtime(*, project_app_id, active_only):
        assert project_app_id == 30
        assert active_only is True
        return runtime

    service.access_repository.get_access_credential_by_client_id = _get_credential
    service.project_repository = SimpleNamespace(get_runtime_by_app_id=_get_runtime)
    service.access_service = SimpleNamespace(
        verify_client_secret=lambda item, secret: item is credential and secret == "sfs_secret"
    )
    captured = {}

    def _create_widget_token(**kwargs):
        captured.update(kwargs)
        return "widget-token"

    monkeypatch.setattr(
        "app.application.integration_bootstrap_service.create_widget_token",
        _create_widget_token,
    )

    result = await service.create_bootstrap(
        client_id="sfc_client",
        client_secret="sfs_secret",
        payload=IntegrationBootstrapCreate(
            principal=IntegrationPrincipal(
                external_user_id="user-1",
                display_name="张三",
            ),
            scope={"store_id": "store-1", "warehouse_id": "warehouse-2"},
            initial_page_type="order-detail",
        ),
    )

    assert result.access_token == "widget-token"
    assert captured["team_id"] == 1
    assert captured["client_id"] == "sfc_client"
    assert captured["product_id"] == 10
    assert captured["project_id"] == 20
    assert captured["project_app_id"] == 30
    assert captured["trusted_scope"]["warehouse_id"] == "warehouse-2"
    assert captured["token_version"] == 4
    assert result.widget_version == "1.0.0"


def test_page_context_accepts_project_specific_attributes():
    context = WidgetPageContext(
        page_type="inventory-detail",
        entity_type="batch",
        entity_id="batch-1",
        attributes={"warehouse_id": "warehouse-2", "selected_tab": "expiry"},
    )

    assert context.attributes["warehouse_id"] == "warehouse-2"


def test_page_context_rejects_more_than_30_nested_keys():
    with pytest.raises(ValidationError, match="more than 30 fields"):
        WidgetPageContext(
            page_type="inventory-detail",
            attributes={"filters": {f"field_{index}": index for index in range(31)}},
        )


def test_widget_access_rejects_stale_token_version():
    credential = SimpleNamespace(
        enabled=True,
        token_version=2,
        allowed_origins=["https://admin.example.com"],
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_widget_access(
            credential=credential,
            token_payload={"token_version": 1},
            origin="https://admin.example.com",
        )

    assert exc_info.value.status_code == 401


def test_widget_access_rejects_unlisted_origin():
    credential = SimpleNamespace(
        enabled=True,
        token_version=1,
        allowed_origins=["https://admin.example.com"],
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_widget_access(
            credential=credential,
            token_payload={"token_version": 1},
            origin="https://other.example.com",
        )

    assert exc_info.value.status_code == 403
