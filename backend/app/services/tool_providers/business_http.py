"""Adapter for the internal Agent Tools HTTP contract."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from app.services.tool_providers.http_client import ProviderHttpClient
from app.services.tool_providers.schemas import (
    DiscoveredTool,
    ToolCallResult,
    ToolProviderConfig,
    ToolProviderError,
)

_ALLOWED_CONTEXT = {
    "external_user_id",
    "project_app_id",
    "project_id",
    "request_id",
    "session_id",
    "store_id",
}
_RESERVED_ARGUMENTS = _ALLOWED_CONTEXT | {"role", "permission", "tenant_id", "user_id"}
_ALLOWED_ACTIONS = {"query", "create", "update", "delete", "approve", "cancel", "refund", "execute"}
_DOMAIN_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,49}$")


class BusinessHttpAdapter:
    """Translate Agent Tools manifest and execute responses."""

    def __init__(self, http_client: ProviderHttpClient) -> None:
        self.http_client = http_client

    async def discover_tools(self, provider: ToolProviderConfig) -> list[DiscoveredTool]:
        response = await self.http_client.request_json(
            method="GET",
            url=self.http_client.build_url(provider.base_url, "manifest"),
            headers={"Accept": "application/json", **self.http_client.build_auth_headers(provider)},
        )
        if response.status_code != 200:
            raise ToolProviderError(f"工具清单请求失败：HTTP {response.status_code}")
        manifest = response.data
        if manifest.get("contract_version") != "1.0":
            raise ToolProviderError("业务端 Agent Tools 契约版本不受支持")
        tools = manifest.get("tools")
        if not isinstance(tools, list):
            raise ToolProviderError("业务端 manifest.tools 必须是数组")
        discovered = [self._parse_tool(item) for item in tools]
        names = [tool.external_name for tool in discovered]
        if len(names) != len(set(names)):
            raise ToolProviderError("业务端 manifest 中存在重复工具名称")
        return discovered

    async def call_tool(
        self,
        provider: ToolProviderConfig,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> ToolCallResult:
        started = time.perf_counter()
        response = await self.http_client.request_json(
            method="POST",
            url=self.http_client.build_url(provider.base_url, "execute"),
            headers={"Accept": "application/json", **self.http_client.build_auth_headers(provider)},
            payload={
                "contract_version": "1.0",
                "name": tool_name,
                "arguments": arguments,
                "context": context,
            },
        )
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        if 200 <= response.status_code < 300 and response.data.get("success") is True:
            data = response.data.get("data")
            return ToolCallResult(
                success=True,
                data=data if isinstance(data, dict) else {"value": data},
                http_status=response.status_code,
                duration_ms=duration_ms,
            )
        error = response.data.get("error") if isinstance(response.data.get("error"), dict) else {}
        error_code = str(error.get("type") or "UPSTREAM_ERROR")
        message = str(error.get("message") or error.get("reason") or "业务工具执行失败")
        return ToolCallResult(
            success=False,
            error_code=error_code,
            message=message,
            retryable=error_code == "INVALID_PARAMS",
            http_status=response.status_code,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _parse_tool(item: Any) -> DiscoveredTool:
        if not isinstance(item, dict):
            raise ToolProviderError("manifest.tools 中存在无效工具定义")
        name = str(item.get("name") or "").strip()
        display_name = str(item.get("display_name") or name).strip()
        domain = str(item.get("domain") or "general").strip().lower()
        action = str(item.get("action") or "execute").strip().lower()
        read_only = item.get("read_only", False)
        required_permissions = item.get("required_permissions") or []
        input_schema = item.get("input_schema")
        output_schema = item.get("output_schema") or {}
        required_context = item.get("required_context") or []
        if not name or not isinstance(input_schema, dict) or not isinstance(output_schema, dict):
            raise ToolProviderError("工具名称和 Schema 必须符合契约")
        if not display_name:
            raise ToolProviderError(f"工具 {name} 的 display_name 不能为空")
        if not _DOMAIN_PATTERN.fullmatch(domain):
            raise ToolProviderError(f"工具 {name} 的 domain 格式无效")
        if action not in _ALLOWED_ACTIONS:
            raise ToolProviderError(f"工具 {name} 的 action 不受支持")
        if not isinstance(read_only, bool):
            raise ToolProviderError(f"工具 {name} 的 read_only 必须是布尔值")
        if read_only and action != "query":
            raise ToolProviderError(f"工具 {name} 的 read_only 与 action 冲突")
        if not isinstance(required_permissions, list) or any(
            not isinstance(permission, str) or not permission.strip()
            for permission in required_permissions
        ):
            raise ToolProviderError(f"工具 {name} 的 required_permissions 必须是非空字符串数组")
        required_permissions = list(dict.fromkeys(permission.strip() for permission in required_permissions))
        properties = input_schema.get("properties") or {}
        if not isinstance(properties, dict):
            raise ToolProviderError(f"工具 {name} 的 input_schema.properties 必须是对象")
        reserved = sorted(_RESERVED_ARGUMENTS.intersection(properties))
        if reserved:
            raise ToolProviderError(f"工具 {name} 不能声明可信上下文字段：{', '.join(reserved)}")
        if not isinstance(required_context, list) or any(
            str(field) not in _ALLOWED_CONTEXT for field in required_context
        ):
            raise ToolProviderError(f"工具 {name} 声明了不允许的可信上下文字段")
        canonical = {
            "domain": domain,
            "action": action,
            "read_only": read_only,
            "required_permissions": required_permissions,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "required_context": required_context,
        }
        schema_hash = hashlib.sha256(
            json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return DiscoveredTool(
            external_name=name,
            external_display_name=display_name,
            description=str(item.get("description") or "").strip() or None,
            domain=domain,
            action=action,
            read_only=read_only,
            required_permissions=required_permissions,
            input_schema=input_schema,
            output_schema=output_schema,
            required_context=[str(field) for field in required_context],
            raw_manifest=item,
            schema_hash=schema_hash,
        )
