"""MCP gateway for Agent tool execution."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from app.application.business_operations.schemas import (
    BusinessOperationDefinition,
    BusinessOperationErrorPayload,
    BusinessOperationRequest,
    BusinessOperationResult,
)
from app.db.models import AgentTool, AgentToolCallLog, McpServer, McpTool
from app.db.session import AsyncSessionLocal
from app.repositories.agent_integration_repository import AgentIntegrationRepository
from app.utils.time import utc_now

_SENSITIVE_KEYS = ("authorization", "token", "password", "secret", "cookie", "api_key", "apikey")
_MAX_LOG_PAYLOAD_CHARS = 12000


@dataclass(slots=True)
class McpCallPayload:
    tool_name: str
    arguments: dict[str, Any]
    request_payload: dict[str, Any]


class McpToolGateway:
    """Call MCP tools and persist redacted Agent tool audit logs."""

    def __init__(self, *, timeout_seconds: float = 12.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def test_server(
        self,
        server: McpServer,
        *,
        service_token: str | None = None,
    ) -> tuple[bool, int | None, int, str, list[dict[str, Any]]]:
        started = time.perf_counter()
        try:
            response = await self._request(
                server=server,
                method="tools/list",
                params={},
                service_token=service_token,
            )
        except (ValueError, httpx.HTTPError) as exc:
            return False, None, self._duration_ms(started), f"MCP 服务连接失败：{exc}", []
        duration_ms = self._duration_ms(started)
        if "error" in response:
            message = self._json_rpc_error_message(response["error"])
            return False, None, duration_ms, f"MCP Server 返回错误：{message}", []
        tools = self._extract_tools(response.get("result"))
        return True, 200, duration_ms, f"已连接到 MCP Server，发现 {len(tools)} 个工具。", tools

    async def call_tool(
        self,
        *,
        server: McpServer,
        mcp_tool: McpTool,
        arguments: dict[str, Any],
        service_token: str | None = None,
        trusted_context: dict[str, Any] | None = None,
    ) -> BusinessOperationResult:
        started = time.perf_counter()
        tool_name = self._normalize_tool_name(mcp_tool.raw_name)
        logger.bind(agent_mcp_log=True).info(
            "[MCP调用] 准备调用工具 | tool={} | arguments={}",
            tool_name,
            arguments,
        )
        try:
            response = await self._request(
                server=server,
                method="tools/call",
                params={"name": tool_name, "arguments": arguments},
                service_token=service_token,
                trusted_context=trusted_context,
            )
        except (ValueError, httpx.HTTPError) as exc:
            return self._error_result(
                operation_id=tool_name,
                code="MCP_CALL_FAILED",
                message=f"MCP 工具调用失败：{exc}",
                retryable=True,
                duration_ms=self._duration_ms(started),
            )
        duration_ms = self._duration_ms(started)
        if "error" in response:
            error = response["error"]
            message = self._json_rpc_error_message(error)
            is_invalid_params = self._json_rpc_error_code(error) == -32602
            return self._error_result(
                operation_id=tool_name,
                code="MCP_INVALID_PARAMS" if is_invalid_params else "MCP_TOOL_ERROR",
                message=(
                    "业务查询参数不符合工具要求。"
                    if is_invalid_params
                    else f"MCP Server 返回错误：{message}"
                ),
                retryable=is_invalid_params,
                duration_ms=duration_ms,
                details={"server_message": message},
            )
        raw_result = response.get("result")
        tool_error = self._extract_tool_result_error(raw_result)
        if tool_error is not None:
            error_code, message = tool_error
            is_invalid_params = self._is_invalid_params_error(error_code, message)
            return self._error_result(
                operation_id=tool_name,
                code="MCP_INVALID_PARAMS" if is_invalid_params else "MCP_TOOL_ERROR",
                message=(
                    "业务查询参数不符合工具要求。"
                    if is_invalid_params
                    else f"MCP 工具执行失败：{message}"
                ),
                retryable=is_invalid_params,
                duration_ms=duration_ms,
                details={"server_message": message, "server_code": error_code},
            )
        data = self._normalize_tool_result(raw_result)
        return BusinessOperationResult(
            success=True,
            operation_id=tool_name,
            message=f"已调用 MCP 工具“{tool_name}”。",
            data=data if isinstance(data, dict) else {"value": data},
            http_status=200,
            duration_ms=duration_ms,
        )

    async def execute(
        self,
        *,
        operation: BusinessOperationDefinition,
        agent_tool: AgentTool,
        mcp_tool: McpTool,
        server: McpServer,
        request: BusinessOperationRequest,
        service_token: str | None,
        record_call: bool = True,
    ) -> BusinessOperationResult:
        payload = self._build_call_payload(mcp_tool=mcp_tool, request=request)
        result = await self.call_tool(
            server=server,
            mcp_tool=mcp_tool,
            arguments=payload.arguments,
            service_token=service_token,
            trusted_context={
                "store_id": request.scope.get("store_id"),
                "external_user_id": request.actor.external_user_id,
                "project_app_id": request.project_app_id or request.scope.get("project_app_id"),
                "project_id": request.scope.get("project_id"),
            },
        )
        result.operation_id = operation.id
        if record_call:
            await self._write_call_log(
                agent_tool=agent_tool,
                mcp_tool=mcp_tool,
                server=server,
                request=request,
                request_payload=payload.request_payload,
                result=result,
            )
        return result

    async def _request(
        self,
        *,
        server: McpServer,
        method: str,
        params: dict[str, Any],
        service_token: str | None = None,
        trusted_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        endpoint = self._normalize_endpoint(server.endpoint_url)
        auth_headers = self._build_auth_headers(server, service_token)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **auth_headers,
            **self._build_context_headers(trusted_context or {}),
        }
        payload = {
            "jsonrpc": "2.0",
            "id": f"agent-gateway-{int(time.time() * 1000)}",
            "method": method,
            "params": params,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=False) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("MCP Server 响应不是 JSON-RPC 对象")
        return data

    @staticmethod
    def _normalize_endpoint(endpoint_url: str) -> str:
        normalized = str(endpoint_url or "").strip()
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("MCP Server 地址必须是有效的 HTTP 或 HTTPS 地址")
        if parsed.username or parsed.password:
            raise ValueError("MCP Server 地址不能包含用户名或密码")
        return normalized

    @staticmethod
    def _normalize_tool_name(raw_name: str) -> str:
        tool_name = str(raw_name or "").strip()
        if not tool_name:
            raise ValueError("MCP 工具名不能为空")
        return tool_name

    @staticmethod
    def _build_auth_headers(
        server: McpServer,
        service_token: str | None,
    ) -> dict[str, str]:
        auth_type = str(server.auth_type or "none").strip().lower()
        if auth_type == "none":
            return {}
        secret = str(service_token or "").strip()
        if not secret:
            raise ValueError("MCP 服务未配置内部服务 Token")
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {secret}"}
        if auth_type == "header":
            header_name = str(server.auth_header_name or "").strip()
            if not header_name:
                raise ValueError("自定义请求头名称不能为空")
            return {header_name: secret}
        raise ValueError("不支持的 MCP 服务鉴权方式")

    @staticmethod
    def _build_context_headers(context: dict[str, Any]) -> dict[str, str]:
        header_map = {
            "store_id": "X-Agent-Store-Id",
            "external_user_id": "X-Agent-User-Id",
            "project_app_id": "X-Agent-Project-App-Id",
            "project_id": "X-Agent-Project-Id",
        }
        return {
            header_name: str(context[key]).strip()
            for key, header_name in header_map.items()
            if context.get(key) is not None and str(context[key]).strip()
        }

    def _build_call_payload(self, *, mcp_tool: McpTool, request: BusinessOperationRequest) -> McpCallPayload:
        tool_name = self._normalize_tool_name(mcp_tool.raw_name)
        arguments = {key: value for key, value in request.params.items() if value is not None}
        return McpCallPayload(tool_name=tool_name, arguments=arguments, request_payload={"tool": tool_name, "arguments": arguments})

    @staticmethod
    def _normalize_tool_result(result: Any) -> Any:
        if not isinstance(result, dict):
            return result
        if isinstance(result.get("structuredContent"), dict):
            return result["structuredContent"]
        if isinstance(result.get("content"), list):
            texts = []
            for item in result["content"]:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(str(item.get("text") or ""))
            if len(texts) == 1:
                text = texts[0].strip()
                try:
                    parsed = json.loads(text)
                    return parsed if isinstance(parsed, dict) else {"text": text}
                except ValueError:
                    return {"text": text}
            if texts:
                return {"text": "\n".join(texts)}
        return result

    @classmethod
    def _extract_tool_result_error(cls, result: Any) -> tuple[str | None, str] | None:
        if not isinstance(result, dict) or result.get("isError") is not True:
            return None
        structured = result.get("structuredContent")
        error_payload = structured.get("error") if isinstance(structured, dict) else None
        if not isinstance(error_payload, dict) and isinstance(structured, dict):
            error_payload = structured
        code = (
            str(error_payload.get("code") or "").strip() or None
            if isinstance(error_payload, dict)
            else None
        )
        message = (
            str(error_payload.get("message") or "").strip()
            if isinstance(error_payload, dict)
            else ""
        )
        if not message:
            normalized = cls._normalize_tool_result(result)
            if isinstance(normalized, dict):
                message = str(normalized.get("text") or normalized.get("message") or "").strip()
        return code, message or "未知错误"

    @staticmethod
    def _is_invalid_params_error(code: str | None, message: str) -> bool:
        normalized_code = str(code or "").strip().upper()
        if normalized_code in {
            "INVALID_ARGUMENT",
            "INVALID_PARAMS",
            "PARAM_VALIDATION_ERROR",
            "VALIDATION_ERROR",
        }:
            return True
        normalized_message = str(message or "").lower()
        return any(
            marker in normalized_message
            for marker in (
                "invalid params",
                "input should be",
                "not one of",
                "literal_error",
                "validation error",
                "参数校验",
                "参数不合法",
            )
        )

    @staticmethod
    def _extract_tools(result: Any) -> list[dict[str, Any]]:
        if not isinstance(result, dict):
            return []
        tools = result.get("tools")
        return [item for item in tools if isinstance(item, dict) and str(item.get("name") or "").strip()] if isinstance(tools, list) else []

    @staticmethod
    def _json_rpc_error_message(error: Any) -> str:
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or "未知错误")
        return str(error or "未知错误")

    @staticmethod
    def _json_rpc_error_code(error: Any) -> int | None:
        if not isinstance(error, dict):
            return None
        code = error.get("code")
        return code if isinstance(code, int) else None

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))

    @staticmethod
    def _error_result(
        *,
        operation_id: str,
        code: str,
        message: str,
        retryable: bool,
        http_status: int | None = None,
        duration_ms: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> BusinessOperationResult:
        return BusinessOperationResult(
            success=False,
            operation_id=operation_id,
            message=message,
            error=BusinessOperationErrorPayload(
                code=code,
                message=message,
                retryable=retryable,
                details=details or {},
            ),
            http_status=http_status,
            duration_ms=duration_ms,
        )

    async def _write_call_log(
        self,
        *,
        agent_tool: AgentTool,
        mcp_tool: McpTool,
        server: McpServer,
        request: BusinessOperationRequest,
        request_payload: dict[str, Any],
        result: BusinessOperationResult,
    ) -> None:
        async with AsyncSessionLocal() as db:
            repository = AgentIntegrationRepository(db)
            confirmed = request.scope.get("confirmed") is True
            await repository.create_call_log(
                AgentToolCallLog(
                    team_id=agent_tool.team_id,
                    project_app_id=request.project_app_id or request.scope.get("project_app_id"),
                    agent_tool_id=agent_tool.id,
                    mcp_server_id=server.id,
                    session_id=request.session_id,
                    trace_id=str(request.scope.get("trace_id") or "") or None,
                    actor_user_id=request.actor.user_id,
                    external_user_id=request.actor.external_user_id,
                    tool_key=agent_tool.tool_key,
                    mcp_tool_name=mcp_tool.raw_name,
                    status="success" if result.success else "error",
                    duration_ms=result.duration_ms,
                    request_payload=self._safe_log_payload(request_payload),
                    response_payload=self._safe_log_payload(result.data),
                    error_message=(result.error.message if result.error else None),
                    confirmed=confirmed,
                    confirmed_at=utc_now() if confirmed else None,
                )
            )

    def _safe_log_payload(self, value: Any) -> dict[str, Any]:
        redacted = self._redact(value)
        normalized = redacted if isinstance(redacted, dict) else {"value": redacted}
        serialized = json.dumps(normalized, ensure_ascii=False, default=str)
        if len(serialized) <= _MAX_LOG_PAYLOAD_CHARS:
            return normalized
        return {"_truncated": True, "preview": serialized[:_MAX_LOG_PAYLOAD_CHARS]}

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): "***" if any(sensitive in str(key).lower() for sensitive in _SENSITIVE_KEYS) else self._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact(item) for item in value[:200]]
        if isinstance(value, str):
            return value[:4000]
        return value
