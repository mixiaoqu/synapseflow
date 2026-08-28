import pytest

from app.services.tool_providers.business_http import BusinessHttpAdapter
from app.services.tool_providers.mcp_http import McpHttpAdapter
from app.services.tool_providers.schemas import ToolProviderError


def _business_tool(**overrides):
    item = {
        "name": "query_orders",
        "display_name": "查询订单",
        "description": "查询当前门店订单",
        "domain": "order",
        "action": "query",
        "read_only": True,
        "required_permissions": ["order:read"],
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "required_context": ["store_id", "external_user_id"],
    }
    item.update(overrides)
    return item


def test_business_http_parses_business_metadata_and_hashes_behavior():
    discovered = BusinessHttpAdapter._parse_tool(_business_tool())

    assert discovered.external_display_name == "查询订单"
    assert discovered.domain == "order"
    assert discovered.action == "query"
    assert discovered.read_only is True
    assert discovered.required_permissions == ["order:read"]

    changed = BusinessHttpAdapter._parse_tool(
        _business_tool(required_permissions=["order:read", "order:special:read"])
    )
    assert changed.schema_hash != discovered.schema_hash


def test_business_http_rejects_invalid_or_conflicting_metadata():
    with pytest.raises(ToolProviderError, match="action"):
        BusinessHttpAdapter._parse_tool(_business_tool(action="manage"))

    with pytest.raises(ToolProviderError, match="read_only"):
        BusinessHttpAdapter._parse_tool(_business_tool(action="refund", read_only=True))

    with pytest.raises(ToolProviderError, match="required_permissions"):
        BusinessHttpAdapter._parse_tool(_business_tool(required_permissions="order:read"))


def test_mcp_tools_receive_conservative_metadata_defaults():
    discovered = McpHttpAdapter._parse_tool({
        "name": "legacy_tool",
        "description": "Legacy MCP tool",
        "inputSchema": {"type": "object", "properties": {}},
    })

    assert discovered.external_display_name == "legacy_tool"
    assert discovered.domain == "general"
    assert discovered.action == "execute"
    assert discovered.read_only is False
    assert discovered.required_permissions == []
