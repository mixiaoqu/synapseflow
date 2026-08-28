from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.application.agent_tool_catalog_service import AgentToolCatalogService
from app.db.models import AgentTool, ToolProvider
from app.repositories.agent_tool_repository import AgentToolRecord


class FakePermissionService:
    def __init__(self, allowed_team_ids: set[int]) -> None:
        self.allowed_team_ids = allowed_team_ids

    async def can_access_team(self, user, team_id: int) -> bool:
        return team_id in self.allowed_team_ids


class FakeRepository:
    def __init__(self) -> None:
        self.list_providers_called = False
        self.saved_tools: list[AgentTool] = []

    async def list_providers(self, **filters):
        self.list_providers_called = True
        return [], 0

    async def get_tool_record(self, tool_id: int):
        provider = ToolProvider(id=3, team_id=9, code="orders", name="订单")
        tool = AgentTool(
            id=tool_id,
            provider_id=provider.id,
            team_id=9,
            external_name="query_orders",
            external_display_name="查询订单",
            tool_key="orders_query_orders",
            name="查询订单",
            schema_hash="schema",
            sync_status="active",
            publish_status="draft",
        )
        return AgentToolRecord(tool=tool, provider=provider, team_name="其他团队")

    async def save_tool(self, tool: AgentTool) -> None:
        self.saved_tools.append(tool)


def _service(*, allowed_team_ids: set[int]) -> AgentToolCatalogService:
    service = AgentToolCatalogService.__new__(AgentToolCatalogService)
    service.user = SimpleNamespace(id=1, role="operator")
    service.permission_service = FakePermissionService(allowed_team_ids)
    service.repository = FakeRepository()
    return service


@pytest.mark.asyncio
async def test_list_providers_rejects_team_outside_current_user_scope():
    service = _service(allowed_team_ids={7})

    with pytest.raises(HTTPException, match="Team access denied") as exc_info:
        await service.list_providers(
            team_id=9,
            keyword=None,
            health_status="all",
            page=1,
            page_size=20,
        )

    assert exc_info.value.status_code == 403
    assert service.repository.list_providers_called is False


@pytest.mark.asyncio
async def test_publish_tool_rejects_tool_outside_current_user_scope():
    service = _service(allowed_team_ids={7})

    with pytest.raises(HTTPException, match="Team access denied") as exc_info:
        await service.publish_tool(5)

    assert exc_info.value.status_code == 403
    assert service.repository.saved_tools == []
