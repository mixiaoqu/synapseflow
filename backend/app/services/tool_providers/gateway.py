"""Protocol selection for external tool providers."""

from __future__ import annotations

from typing import Any, Protocol

from app.services.tool_providers.business_http import BusinessHttpAdapter
from app.services.tool_providers.http_client import ProviderHttpClient
from app.services.tool_providers.mcp_http import McpHttpAdapter
from app.services.tool_providers.schemas import (
    DiscoveredTool,
    ToolCallResult,
    ToolProviderConfig,
    ToolProviderError,
)


class ToolProviderAdapter(Protocol):
    async def discover_tools(self, provider: ToolProviderConfig) -> list[DiscoveredTool]: ...

    async def call_tool(
        self,
        provider: ToolProviderConfig,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> ToolCallResult: ...


class ToolProviderGateway:
    """Select the configured provider adapter without leaking protocol details."""

    def __init__(self, http_client: ProviderHttpClient | None = None) -> None:
        client = http_client or ProviderHttpClient()
        self.adapters: dict[str, ToolProviderAdapter] = {
            "business_http": BusinessHttpAdapter(client),
            "mcp_http": McpHttpAdapter(client),
        }

    def _adapter(self, transport_type: str) -> ToolProviderAdapter:
        adapter = self.adapters.get(str(transport_type or "").strip())
        if adapter is None:
            raise ToolProviderError("不支持的工具提供方接入类型")
        return adapter

    async def discover_tools(self, provider: ToolProviderConfig) -> list[DiscoveredTool]:
        return await self._adapter(provider.transport_type).discover_tools(provider)

    async def call_tool(
        self,
        provider: ToolProviderConfig,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> ToolCallResult:
        return await self._adapter(provider.transport_type).call_tool(
            provider,
            tool_name,
            arguments,
            context,
        )

