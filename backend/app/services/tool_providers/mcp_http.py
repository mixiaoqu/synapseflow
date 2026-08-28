"""Adapter for HTTP JSON-RPC MCP providers."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.services.tool_providers.http_client import ProviderHttpClient
from app.services.tool_providers.schemas import (
    DiscoveredTool,
    ToolCallResult,
    ToolProviderConfig,
    ToolProviderError,
)


class McpHttpAdapter:
    """Translate MCP tools/list and tools/call messages."""

    def __init__(self, http_client: ProviderHttpClient) -> None:
        self.http_client = http_client

    async def discover_tools(self, provider: ToolProviderConfig) -> list[DiscoveredTool]:
        response = await self._request(provider, "tools/list", {})
        if "error" in response:
            raise ToolProviderError(self._error_message(response["error"]))
        result = response.get("result")
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            raise ToolProviderError("MCP tools/list 未返回工具数组")
        return [self._parse_tool(item) for item in tools]

    async def call_tool(
        self,
        provider: ToolProviderConfig,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> ToolCallResult:
        started = time.perf_counter()
        response = await self._request(
            provider,
            "tools/call",
            {"name": tool_name, "arguments": arguments},
            context=context,
        )
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        if "error" in response:
            error = response["error"]
            invalid = isinstance(error, dict) and error.get("code") == -32602
            return ToolCallResult(
                success=False,
                error_code="INVALID_PARAMS" if invalid else "UPSTREAM_ERROR",
                message=self._error_message(error),
                retryable=invalid,
                duration_ms=duration_ms,
            )
        result = response.get("result")
        if isinstance(result, dict) and result.get("isError") is True:
            return ToolCallResult(
                success=False,
                error_code="UPSTREAM_ERROR",
                message=self._tool_error_message(result),
                duration_ms=duration_ms,
            )
        data = self._normalize_result(result)
        return ToolCallResult(
            success=True,
            data=data if isinstance(data, dict) else {"value": data},
            http_status=200,
            duration_ms=duration_ms,
        )

    async def _request(
        self,
        provider: ToolProviderConfig,
        method: str,
        params: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self.http_client.build_auth_headers(provider),
        }
        source = (context or {}).get("source")
        if isinstance(source, dict) and source.get("request_id"):
            headers["X-Request-Id"] = str(source["request_id"])
        response = await self.http_client.request_json(
            method="POST",
            url=self.http_client.build_url(provider.base_url),
            headers=headers,
            payload={
                "jsonrpc": "2.0",
                "id": f"synapseflow-{int(time.time() * 1000)}",
                "method": method,
                "params": params,
            },
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise ToolProviderError(f"MCP 请求失败：HTTP {response.status_code}")
        return response.data

    @staticmethod
    def _parse_tool(item: Any) -> DiscoveredTool:
        if not isinstance(item, dict):
            raise ToolProviderError("MCP 工具定义无效")
        name = str(item.get("name") or "").strip()
        input_schema = item.get("inputSchema") or item.get("input_schema") or {}
        output_schema = item.get("outputSchema") or item.get("output_schema") or {}
        if not name or not isinstance(input_schema, dict) or not isinstance(output_schema, dict):
            raise ToolProviderError("MCP 工具名称或 Schema 无效")
        canonical = {
            "domain": "general",
            "action": "execute",
            "read_only": False,
            "required_permissions": [],
            "input_schema": input_schema,
            "output_schema": output_schema,
            "required_context": [],
        }
        schema_hash = hashlib.sha256(
            json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return DiscoveredTool(
            external_name=name,
            external_display_name=name,
            description=str(item.get("description") or "").strip() or None,
            domain="general",
            action="execute",
            read_only=False,
            required_permissions=[],
            input_schema=input_schema,
            output_schema=output_schema,
            required_context=[],
            raw_manifest=item,
            schema_hash=schema_hash,
        )

    @staticmethod
    def _error_message(error: Any) -> str:
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or "MCP 请求失败")
        return str(error or "MCP 请求失败")

    @classmethod
    def _tool_error_message(cls, result: dict[str, Any]) -> str:
        normalized = cls._normalize_result(result)
        if isinstance(normalized, dict):
            return str(normalized.get("message") or normalized.get("text") or "MCP 工具执行失败")
        return "MCP 工具执行失败"

    @staticmethod
    def _normalize_result(result: Any) -> Any:
        if not isinstance(result, dict):
            return result
        if isinstance(result.get("structuredContent"), dict):
            return result["structuredContent"]
        content = result.get("content")
        if isinstance(content, list):
            texts = [
                str(item.get("text") or "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            if len(texts) == 1:
                try:
                    return json.loads(texts[0])
                except json.JSONDecodeError:
                    return {"text": texts[0]}
            if texts:
                return {"text": "\n".join(texts)}
        return result
