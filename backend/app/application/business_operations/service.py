"""Application service for controlled business data operations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import exceptions as jsonschema_exceptions
from jsonschema import validators
from loguru import logger

from app.application.business_operations.mcp_tool_gateway import McpToolGateway
from app.application.business_operations.registry import (
    AGENT_CONTEXT_PARAM_KEYS,
    BusinessOperationRegistry,
)
from app.application.business_operations.schemas import (
    BusinessOperationDefinition,
    BusinessOperationErrorPayload,
    BusinessOperationMissingField,
    BusinessOperationRequest,
    BusinessOperationResult,
)
from app.core.credential_cipher import CredentialCipher
from app.db.session import AsyncSessionLocal
from app.repositories.agent_integration_repository import (
    AgentIntegrationRepository,
    AgentToolExecutionRecord,
)


class BusinessOperationService:
    """Discover, validate and execute tools from MCP tool sets bound to the current app."""

    def __init__(self, *, registry: BusinessOperationRegistry | None = None, mcp_tool_gateway: McpToolGateway | None = None) -> None:
        self.registry = registry or BusinessOperationRegistry()
        self.mcp_tool_gateway = mcp_tool_gateway or McpToolGateway()
        self.credential_cipher = CredentialCipher()

    async def list_available_tools(self, project_app_id: int | None) -> list[AgentToolExecutionRecord]:
        if project_app_id is None:
            return []
        async with AsyncSessionLocal() as db:
            repository = AgentIntegrationRepository(db)
            return await repository.list_available_project_app_tools(project_app_id=int(project_app_id))

    async def list_available_operations(self, project_app_id: int | None) -> list[BusinessOperationDefinition]:
        records = await self.list_available_tools(project_app_id)
        return self.registry.list_from_records(records)

    async def get_tool_availability_snapshot(self, project_app_id: int | None) -> dict[str, Any]:
        if project_app_id is None:
            return {
                "project_app_id": None,
                "tool_set_count": 0,
                "available_count": 0,
                "unavailable_count": 0,
                "available_tool_keys": [],
                "unavailable_reason_counts": {},
            }
        async with AsyncSessionLocal() as db:
            repository = AgentIntegrationRepository(db)
            tool_set_records = await repository.list_project_app_tool_set_bindings(
                project_app_id=int(project_app_id)
            )
            available_records = await repository.list_available_project_app_tools(
                project_app_id=int(project_app_id)
            )
        available_tool_keys = [record.tool.tool_key for record in available_records]
        unavailable_reason_counts: dict[str, int] = {}
        for record in tool_set_records:
            if record.unavailable_reason:
                unavailable_reason_counts[record.unavailable_reason] = (
                    unavailable_reason_counts.get(record.unavailable_reason, 0) + 1
                )
        return {
            "project_app_id": int(project_app_id),
            "tool_set_count": len(tool_set_records),
            "available_count": len(available_tool_keys),
            "unavailable_count": sum(unavailable_reason_counts.values()),
            "available_tool_keys": available_tool_keys,
            "unavailable_reason_counts": unavailable_reason_counts,
        }

    async def execute(self, request: BusinessOperationRequest) -> BusinessOperationResult:
        project_app_id = request.project_app_id or request.scope.get("project_app_id")
        record = await self._get_available_tool(project_app_id=project_app_id, operation_id=request.operation_id)
        if record is None:
            return BusinessOperationResult(
                success=False,
                operation_id=request.operation_id,
                message="当前应用端未绑定对应工具集，或工具尚未启用。",
                error=BusinessOperationErrorPayload(code="TOOL_NOT_AVAILABLE", message="当前应用端未绑定对应工具集，或工具尚未启用。"),
            )

        operation = self.registry.from_tool_record(record)
        effective_request = self._with_schema_defaults(
            operation,
            self._without_context_params(request),
        )
        logger.bind(agent_business_ops_log=True).info(
            "[业务工具参数] 已移除上下文参数 | operation={} | request_params={} | effective_params={}",
            operation.id,
            request.params,
            effective_request.params,
        )
        missing_fields = self._collect_missing_fields(operation, effective_request)
        if missing_fields:
            return BusinessOperationResult(
                success=False,
                operation_id=operation.id,
                message="还需要补充必要信息。",
                missing_fields=missing_fields,
                error=BusinessOperationErrorPayload(code="MISSING_PARAMS", message="还需要补充必要信息。", retryable=True),
            )

        try:
            schema_errors = self._collect_schema_errors(operation, effective_request)
        except jsonschema_exceptions.SchemaError as exc:
            logger.exception("[business_ops] invalid tool input schema. operation={}", operation.id)
            return BusinessOperationResult(
                success=False,
                operation_id=operation.id,
                message="业务工具参数定义无效。",
                error=BusinessOperationErrorPayload(
                    code="TOOL_SCHEMA_INVALID",
                    message="业务工具参数定义无效。",
                    details={"schema_error": str(exc)},
                ),
            )
        if schema_errors:
            message = "业务查询参数不符合工具要求。"
            return BusinessOperationResult(
                success=False,
                operation_id=operation.id,
                message=message,
                error=BusinessOperationErrorPayload(
                    code="INVALID_PARAMS",
                    message=message,
                    retryable=True,
                    details={"validation_errors": schema_errors},
                ),
            )

        if operation.requires_confirmation and request.scope.get("confirmed") is not True:
            return BusinessOperationResult(
                success=False,
                operation_id=operation.id,
                message=f"Agent 工具“{operation.name}”需要用户确认后才能执行。",
                error=BusinessOperationErrorPayload(code="CONFIRMATION_REQUIRED", message=f"Agent 工具“{operation.name}”需要用户确认后才能执行。", retryable=True),
            )

        service_token = None
        if str(record.mcp_server.auth_type or "none").strip().lower() != "none":
            if not record.mcp_server.auth_token_encrypted:
                return BusinessOperationResult(
                    success=False,
                    operation_id=operation.id,
                    message="MCP 服务未配置内部服务 Token。",
                    error=BusinessOperationErrorPayload(
                        code="MCP_SERVICE_TOKEN_REQUIRED",
                        message="MCP 服务未配置内部服务 Token。",
                    ),
                )
            try:
                service_token = self.credential_cipher.decrypt(
                    record.mcp_server.auth_token_encrypted
                )
            except ValueError:
                logger.exception(
                    "[business_ops] failed to decrypt MCP credential. operation={}",
                    operation.id,
                )
                return BusinessOperationResult(
                    success=False,
                    operation_id=operation.id,
                    message="MCP 服务 Token 无法解密，请重新填写。",
                    error=BusinessOperationErrorPayload(
                        code="MCP_SERVICE_TOKEN_INVALID",
                        message="MCP 服务 Token 无法解密，请重新填写。",
                    ),
                )

        if not str(request.scope.get("store_id") or "").strip():
            return BusinessOperationResult(
                success=False,
                operation_id=operation.id,
                message="业务工具调用缺少可信门店上下文。",
                error=BusinessOperationErrorPayload(
                    code="BUSINESS_CONTEXT_REQUIRED",
                    message="业务工具调用缺少可信门店上下文。",
                ),
            )

        return await self.mcp_tool_gateway.execute(
            operation=operation,
            agent_tool=record.tool,
            mcp_tool=record.mcp_tool,
            server=record.mcp_server,
            request=effective_request,
            service_token=service_token,
        )

    async def _get_available_tool(self, *, project_app_id: int | str | None, operation_id: str) -> AgentToolExecutionRecord | None:
        if project_app_id is None:
            return None
        async with AsyncSessionLocal() as db:
            repository = AgentIntegrationRepository(db)
            return await repository.get_available_project_app_tool_by_key(project_app_id=int(project_app_id), tool_key=operation_id)

    @staticmethod
    def _is_blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    def _without_context_params(self, request: BusinessOperationRequest) -> BusinessOperationRequest:
        params = {
            key: value
            for key, value in request.params.items()
            if key not in AGENT_CONTEXT_PARAM_KEYS
        }
        return request.model_copy(update={"params": params})

    @staticmethod
    def _with_schema_defaults(
        operation: BusinessOperationDefinition,
        request: BusinessOperationRequest,
    ) -> BusinessOperationRequest:
        params = deepcopy(request.params)
        properties = operation.input_schema.get("properties")
        if not isinstance(properties, dict):
            return request
        for key, spec in properties.items():
            if key not in params and isinstance(spec, dict) and "default" in spec:
                params[key] = deepcopy(spec["default"])
        return request.model_copy(update={"params": params})

    def _collect_missing_fields(self, operation: BusinessOperationDefinition, request: BusinessOperationRequest) -> list[BusinessOperationMissingField]:
        return [
            BusinessOperationMissingField(
                key=param.key,
                label=param.label,
                type=param.type,
                required=param.required,
                description=param.description,
                resolver=param.resolver,
            )
            for param in operation.params
            if param.required and self._is_blank(request.params.get(param.key))
        ]

    @staticmethod
    def _collect_schema_errors(
        operation: BusinessOperationDefinition,
        request: BusinessOperationRequest,
    ) -> list[dict[str, Any]]:
        schema = operation.input_schema or {"type": "object", "properties": {}}
        validator_class = validators.validator_for(schema)
        validator_class.check_schema(schema)
        errors = sorted(
            validator_class(schema).iter_errors(request.params),
            key=lambda item: [str(part) for part in item.absolute_path],
        )
        return [
            {
                "path": ".".join(str(part) for part in error.absolute_path) or "$",
                "rule": str(error.validator or "validation"),
                "message": error.message,
                "allowed_values": (
                    list(error.validator_value)
                    if error.validator == "enum" and isinstance(error.validator_value, list)
                    else []
                ),
            }
            for error in errors
        ]
