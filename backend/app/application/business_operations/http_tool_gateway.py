"""HTTP executor for reusable business tools."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

from app.application.business_operations.schemas import (
    BusinessOperationDefinition,
    BusinessOperationErrorPayload,
    BusinessOperationRequest,
    BusinessOperationResult,
)
from app.db.models import (
    BusinessApi,
    BusinessConnection,
    BusinessTool,
    BusinessToolCallLog,
    BusinessToolImplementation,
)
from app.db.session import AsyncSessionLocal
from app.models.schemas.business_tool import BusinessApiRequestFieldSpec, BusinessApiRequestSchema
from app.repositories.business_tool_repository import BusinessToolRepository

_SENSITIVE_KEYS = ("authorization", "token", "password", "secret", "cookie", "api_key", "apikey")
_MAX_LOG_PAYLOAD_CHARS = 12000


@dataclass(slots=True)
class PreparedHttpRequest:
    url: str
    headers: dict[str, str]
    query_params: dict[str, Any]
    body: dict[str, Any] | None
    log_payload: dict[str, Any]


class BusinessToolGateway:
    """Execute one configured HTTP tool and persist a redacted call record."""

    def __init__(self, *, timeout_seconds: float = 8.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def test_connection(self, connection: BusinessConnection) -> tuple[bool, int | None, int, str]:
        started = time.perf_counter()
        try:
            headers = self._build_headers(connection)
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.get(connection.base_url, headers=headers)
            duration_ms = self._duration_ms(started)
            if response.status_code < 500 and response.status_code not in {401, 403}:
                return (
                    True,
                    response.status_code,
                    duration_ms,
                    f"已连接到业务系统，响应状态为 {response.status_code}。",
                )
            return (
                False,
                response.status_code,
                duration_ms,
                f"业务系统返回异常状态 {response.status_code}。",
            )
        except (ValueError, httpx.HTTPError) as exc:
            return False, None, self._duration_ms(started), f"连接失败：{exc}"

    async def execute(
        self,
        *,
        operation: BusinessOperationDefinition,
        tool: BusinessTool,
        implementation: BusinessToolImplementation,
        api: BusinessApi,
        connection: BusinessConnection,
        request: BusinessOperationRequest,
        record_call: bool = True,
    ) -> BusinessOperationResult:
        started = time.perf_counter()
        raw_payload = self._build_request_payload(
            implementation=implementation,
            request=request,
        )
        try:
            prepared_request = self._prepare_http_request(
                api=api,
                connection=connection,
                payload=raw_payload,
            )
        except ValueError as exc:
            result = self._error_result(
                operation_id=operation.id,
                code="REQUEST_BUILD_FAILED",
                message=str(exc),
                retryable=True,
                duration_ms=self._duration_ms(started),
            )
            if record_call:
                await self._write_call_log(
                    tool=tool,
                    implementation=implementation,
                    api=api,
                    request=request,
                    request_payload={"payload": raw_payload},
                    result=result,
                )
            return result
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await self._send_request(
                    client=client,
                    method=api.method,
                    url=prepared_request.url,
                    query_params=prepared_request.query_params,
                    body=prepared_request.body,
                    headers=prepared_request.headers,
                )
        except httpx.TimeoutException:
            result = self._error_result(
                operation_id=operation.id,
                code="HTTP_TIMEOUT",
                message="业务接口调用超时。",
                retryable=True,
                duration_ms=self._duration_ms(started),
            )
            if record_call:
                await self._write_call_log(
                    tool=tool,
                    implementation=implementation,
                    api=api,
                    request=request,
                    request_payload=prepared_request.log_payload,
                    result=result,
                )
            return result
        except (ValueError, httpx.HTTPError) as exc:
            result = self._error_result(
                operation_id=operation.id,
                code="HTTP_REQUEST_FAILED",
                message=f"业务接口调用失败：{exc}",
                retryable=True,
                duration_ms=self._duration_ms(started),
            )
            if record_call:
                await self._write_call_log(
                    tool=tool,
                    implementation=implementation,
                    api=api,
                    request=request,
                    request_payload=prepared_request.log_payload,
                    result=result,
                )
            return result

        duration_ms = self._duration_ms(started)
        response_payload = self._parse_response(response)
        if response.status_code < 200 or response.status_code >= 300:
            result = self._error_result(
                operation_id=operation.id,
                code="HTTP_STATUS_ERROR",
                message=f"业务接口返回异常状态：{response.status_code}",
                retryable=response.status_code >= 500,
                http_status=response.status_code,
                duration_ms=duration_ms,
            )
            if record_call:
                await self._write_call_log(
                    tool=tool,
                    implementation=implementation,
                    api=api,
                    request=request,
                    request_payload=prepared_request.log_payload,
                    result=result,
                    response_payload=response_payload,
                )
            return result

        data = self._build_response_payload(implementation.response_mapping or {}, response_payload)
        result = BusinessOperationResult(
            success=True,
            operation_id=operation.id,
            message=f"已调用业务工具“{tool.name}”。",
            data=data,
            http_status=response.status_code,
            duration_ms=duration_ms,
        )
        if record_call:
            await self._write_call_log(
                tool=tool,
                implementation=implementation,
                api=api,
                request=request,
                request_payload=prepared_request.log_payload,
                result=result,
                response_payload=response_payload,
            )
        return result

    async def _send_request(
        self,
        *,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        query_params: dict[str, Any],
        body: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        normalized_method = method.upper()
        if normalized_method == "GET":
            return await client.request(
                normalized_method,
                url,
                params=self._encode_query_payload(query_params),
                headers=headers,
            )
        if normalized_method == "DELETE":
            request_kwargs: dict[str, Any] = {
                "params": self._encode_query_payload(query_params),
                "headers": headers,
            }
            if body:
                request_kwargs["json"] = body
            return await client.request(normalized_method, url, **request_kwargs)
        request_kwargs = {
            "params": self._encode_query_payload(query_params),
            "headers": headers,
        }
        if body is not None:
            request_kwargs["json"] = body
        return await client.request(normalized_method, url, **request_kwargs)

    @staticmethod
    def _build_url(base_url: str, path: str, path_params: dict[str, Any] | None = None) -> str:
        parsed_base = urlparse(str(base_url or "").strip())
        if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
            raise ValueError("连接地址必须是有效的 HTTP 或 HTTPS 地址")
        if parsed_base.username or parsed_base.password:
            raise ValueError("连接地址不能包含用户名或密码")

        normalized_path = BusinessToolGateway._resolve_path_params(str(path or "").strip(), path_params or {})
        parsed_path = urlparse(normalized_path)
        if parsed_path.scheme or parsed_path.netloc or normalized_path.startswith("//"):
            raise ValueError("接口路径必须使用连接内的相对路径")
        if not normalized_path:
            return str(base_url).rstrip("/")
        return urljoin(f"{str(base_url).rstrip('/')}/", normalized_path.lstrip("/"))

    @staticmethod
    def _build_headers(connection: BusinessConnection) -> dict[str, str]:
        auth_type = str(connection.auth_type or "none").strip().lower()
        if auth_type == "none":
            return {}
        secret_ref = str(connection.auth_secret_ref or "").strip()
        if not secret_ref:
            raise ValueError("连接未配置密钥环境变量")
        secret = str(os.getenv(secret_ref) or "").strip()
        if not secret:
            raise ValueError(f"环境变量 {secret_ref} 未配置")
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {secret}"}
        if auth_type == "header":
            header_name = str(connection.auth_header_name or "").strip()
            if not header_name:
                raise ValueError("自定义请求头名称不能为空")
            return {header_name: secret}
        raise ValueError("不支持的连接鉴权方式")

    @staticmethod
    def _parse_response(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return {"text": response.text}

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
    ) -> BusinessOperationResult:
        return BusinessOperationResult(
            success=False,
            operation_id=operation_id,
            message=message,
            error=BusinessOperationErrorPayload(
                code=code,
                message=message,
                retryable=retryable,
            ),
            http_status=http_status,
            duration_ms=duration_ms,
        )

    def _build_request_payload(
        self,
        *,
        implementation: BusinessToolImplementation,
        request: BusinessOperationRequest,
    ) -> dict[str, Any]:
        source = {
            "scope": request.scope,
            "params": request.params,
            "actor": request.actor.model_dump(),
        }
        context_payload = self._apply_mapping(implementation.context_binding or {}, source)
        mapping = implementation.request_mapping or {}
        if mapping:
            mapped_payload = self._apply_mapping(mapping, source)
            payload = {**context_payload, **mapped_payload}
        else:
            payload = {**context_payload, **request.params}
        return {key: value for key, value in payload.items() if value is not None}

    def _prepare_http_request(
        self,
        *,
        api: BusinessApi,
        connection: BusinessConnection,
        payload: dict[str, Any],
    ) -> PreparedHttpRequest:
        request_schema = BusinessApiRequestSchema.model_validate(api.request_schema or {})
        connection_headers = self._build_headers(connection)
        if not request_schema.fields:
            url = self._build_url(connection.base_url, api.path)
            if api.method.upper() in {"GET", "DELETE"}:
                query_params = payload
                body = None
            else:
                query_params = {}
                body = payload or None
            return PreparedHttpRequest(
                url=url,
                headers=connection_headers,
                query_params=query_params,
                body=body,
                log_payload={
                    "query": query_params,
                    "headers": connection_headers,
                    "body": body or {},
                },
            )

        path_params: dict[str, Any] = {}
        query_params: dict[str, Any] = {}
        request_headers: dict[str, str] = {}
        body: dict[str, Any] = {}
        missing_fields: list[str] = []

        for field in request_schema.fields:
            value = payload.get(field.name)
            if self._is_blank(value):
                if field.required:
                    missing_fields.append(field.label or field.name)
                continue
            if field.location == "path":
                path_params[field.name] = value
            elif field.location == "query":
                query_params[field.name] = value
            elif field.location == "header":
                request_headers[field.name] = self._stringify_header_value(value, field=field)
            else:
                self._assign_body_value(body, field.name, value)

        if missing_fields:
            raise ValueError(f"业务接口缺少必填字段：{'、'.join(missing_fields)}。")

        url = self._build_url(connection.base_url, api.path, path_params)
        headers = {**request_headers, **connection_headers}
        return PreparedHttpRequest(
            url=url,
            headers=headers,
            query_params=query_params,
            body=body or None,
            log_payload={
                "path": path_params,
                "query": query_params,
                "headers": headers,
                "body": body,
            },
        )

    @staticmethod
    def _encode_query_payload(payload: dict[str, Any]) -> dict[str, Any]:
        encoded: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                encoded[key] = json.dumps(value, ensure_ascii=False)
            else:
                encoded[key] = value
        return encoded

    def _build_response_payload(
        self,
        response_mapping: dict[str, Any],
        response_payload: Any,
    ) -> dict[str, Any]:
        if not response_mapping:
            return response_payload if isinstance(response_payload, dict) else {"value": response_payload}
        source = {"response": response_payload, "data": response_payload}
        return self._apply_mapping(response_mapping, source)

    def _apply_mapping(
        self,
        mapping: dict[str, Any],
        source: dict[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for target_key, source_path in mapping.items():
            if isinstance(source_path, str):
                payload[target_key] = self._lookup_path(source, source_path)
            elif source_path is not None:
                payload[target_key] = source_path
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _resolve_path_params(path: str, path_params: dict[str, Any]) -> str:
        resolved = path
        for key, value in path_params.items():
            encoded = quote(str(value), safe="")
            resolved = resolved.replace(f"{{{key}}}", encoded)
            resolved = resolved.replace(f":{key}", encoded)
        if "{" in resolved and "}" in resolved:
            raise ValueError(f"接口路径仍存在未替换的路径参数：{resolved}")
        return resolved

    @staticmethod
    def _assign_body_value(target: dict[str, Any], path: str, value: Any) -> None:
        if "." not in path:
            target[path] = value
            return
        current = target
        parts = [part for part in path.split(".") if part]
        for part in parts[:-1]:
            next_value = current.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                current[part] = next_value
            current = next_value
        current[parts[-1]] = value

    @staticmethod
    def _stringify_header_value(value: Any, *, field: BusinessApiRequestFieldSpec) -> str:
        if isinstance(value, (dict, list)):
            raise ValueError(f"请求头字段“{field.label or field.name}”不能是对象或数组。")
        return str(value)

    @staticmethod
    def _is_blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _lookup_path(source: dict[str, Any], path: str) -> Any:
        current: Any = source
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                current = current[index] if index < len(current) else None
            else:
                return None
            if current is None:
                return None
        return current

    async def _write_call_log(
        self,
        *,
        tool: BusinessTool,
        implementation: BusinessToolImplementation,
        api: BusinessApi,
        request: BusinessOperationRequest,
        request_payload: dict[str, Any],
        result: BusinessOperationResult,
        response_payload: Any = None,
    ) -> None:
        async with AsyncSessionLocal() as db:
            repository = BusinessToolRepository(db)
            await repository.create_call_log(
                BusinessToolCallLog(
                    team_id=tool.team_id,
                    project_app_id=request.project_app_id or request.scope.get("project_app_id"),
                    business_api_id=api.id,
                    business_tool_id=tool.id,
                    business_tool_implementation_id=implementation.id,
                    tool_key=tool.tool_key,
                    tool_name=tool.name,
                    api_key=api.api_key,
                    api_name=api.name,
                    session_id=request.session_id,
                    actor_user_id=request.actor.user_id,
                    external_user_id=request.actor.external_user_id,
                    status="success" if result.success else "error",
                    http_status=result.http_status,
                    duration_ms=result.duration_ms,
                    request_payload=self._safe_log_payload(request_payload),
                    response_payload=self._safe_log_payload(
                        response_payload if response_payload is not None else result.data
                    ),
                    error_message=(result.error.message if result.error else None),
                )
            )

    def _safe_log_payload(self, value: Any) -> dict[str, Any]:
        redacted = self._redact(value)
        normalized = redacted if isinstance(redacted, dict) else {"value": redacted}
        serialized = json.dumps(normalized, ensure_ascii=False, default=str)
        if len(serialized) <= _MAX_LOG_PAYLOAD_CHARS:
            return normalized
        return {
            "_truncated": True,
            "preview": serialized[:_MAX_LOG_PAYLOAD_CHARS],
        }

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): (
                    "***"
                    if any(sensitive in str(key).lower() for sensitive in _SENSITIVE_KEYS)
                    else self._redact(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact(item) for item in value[:200]]
        if isinstance(value, str):
            return value[:4000]
        return value
