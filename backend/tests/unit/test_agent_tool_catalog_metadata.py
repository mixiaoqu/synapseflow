import pytest

from app.application.agent_tool_catalog_service import AgentToolCatalogService
from app.db.models import AgentTool, ToolProvider
from app.services.tool_providers.schemas import DiscoveredTool


class FakeRepository:
    def __init__(self, provider, tools):
        self.provider = provider
        self.tools = tools
        self.saved = []

    async def get_provider(self, provider_id):
        return self.provider if provider_id == self.provider.id else None

    async def list_tools_for_provider(self, provider_id):
        return self.tools

    async def get_tool_by_key(self, **kwargs):
        return None

    async def save_tools(self, tools):
        self.saved = list(tools)


class FakeGateway:
    def __init__(self, discovered):
        self.discovered = discovered

    async def discover_tools(self, provider):
        return self.discovered


def _discovered(display_name="业务端订单查询", schema_hash="new-hash"):
    return DiscoveredTool(
        external_name="query_orders",
        external_display_name=display_name,
        description="业务端描述",
        domain="order",
        action="query",
        read_only=True,
        required_permissions=["order:read"],
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        required_context=["store_id"],
        raw_manifest={"name": "query_orders"},
        schema_hash=schema_hash,
    )


def _service(provider, tools, discovered):
    service = AgentToolCatalogService.__new__(AgentToolCatalogService)
    service.repository = FakeRepository(provider, tools)
    service.gateway = FakeGateway(discovered)
    return service


@pytest.mark.asyncio
async def test_sync_persists_source_metadata_without_overwriting_governance():
    provider = ToolProvider(
        id=1,
        team_id=2,
        code="medical_center",
        name="医疗中心",
        base_url="https://example.test/agent-tools",
        transport_type="business_http",
        auth_type="none",
    )
    tool = AgentTool(
        provider_id=1,
        team_id=2,
        external_name="query_orders",
        external_description="旧描述",
        input_schema={},
        output_schema={},
        required_context=[],
        raw_manifest={},
        schema_hash="old-hash",
        sync_status="active",
        tool_key="medical_center_query_orders",
        name="管理员自定义名称",
        agent_description="管理员自定义描述",
        risk_level="medium",
        requires_confirmation=True,
        publish_status="published",
    )
    service = _service(provider, [tool], [_discovered()])

    await service.sync_tools(provider.id)

    assert tool.external_display_name == "业务端订单查询"
    assert tool.domain == "order"
    assert tool.action == "query"
    assert tool.read_only is True
    assert tool.required_permissions == ["order:read"]
    assert tool.name == "管理员自定义名称"
    assert tool.agent_description == "管理员自定义描述"
    assert tool.risk_level == "medium"
    assert tool.requires_confirmation is True
    assert tool.publish_status == "needs_review"


@pytest.mark.asyncio
async def test_sync_uses_source_display_name_for_new_tool():
    provider = ToolProvider(
        id=1,
        team_id=2,
        code="medical_center",
        name="医疗中心",
        base_url="https://example.test/agent-tools",
        transport_type="business_http",
        auth_type="none",
    )
    service = _service(provider, [], [_discovered(schema_hash="hash")])

    await service.sync_tools(provider.id)

    tool = service.repository.saved[0]
    assert tool.name == "业务端订单查询"
    assert tool.external_display_name == "业务端订单查询"


@pytest.mark.asyncio
async def test_sync_upgrades_legacy_machine_name_to_source_display_name():
    provider = ToolProvider(
        id=1,
        team_id=2,
        code="medical_center",
        name="医疗中心",
        base_url="https://example.test/agent-tools",
        transport_type="business_http",
        auth_type="none",
    )
    tool = AgentTool(
        provider_id=1,
        team_id=2,
        external_name="query_orders",
        external_display_name="query_orders",
        external_description="旧描述",
        input_schema={},
        output_schema={},
        required_context=[],
        raw_manifest={},
        schema_hash="old-hash",
        sync_status="active",
        tool_key="medical_center_query_orders",
        name="query_orders",
        agent_description="旧描述",
        risk_level="low",
        requires_confirmation=False,
        publish_status="draft",
    )
    service = _service(provider, [tool], [_discovered(display_name="查询订单")])

    await service.sync_tools(provider.id)

    assert tool.name == "查询订单"
