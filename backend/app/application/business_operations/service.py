"""Application service for controlled business data operations."""

from __future__ import annotations

from typing import Any

from app.application.business_operations.http_tool_gateway import BusinessToolGateway
from app.application.business_operations.registry import BusinessOperationRegistry
from app.application.business_operations.schemas import (
    BusinessOperationDefinition,
    BusinessOperationErrorPayload,
    BusinessOperationMissingField,
    BusinessOperationRequest,
    BusinessOperationResult,
)
from app.db.session import AsyncSessionLocal
from app.repositories.business_tool_repository import (
    BusinessToolExecutionRecord,
    BusinessToolRepository,
)


class BusinessOperationService:
    """Discover, validate and execute tools authorized for the current app."""

    def __init__(
        self,
        *,
        registry: BusinessOperationRegistry | None = None,
        http_tool_gateway: BusinessToolGateway | None = None,
    ) -> None:
        self.registry = registry or BusinessOperationRegistry()
        self.http_tool_gateway = http_tool_gateway or BusinessToolGateway()

    async def list_available_tools(self, project_app_id: int | None) -> list[BusinessToolExecutionRecord]:
        if project_app_id is None:
            return []
        async with AsyncSessionLocal() as db:
            repository = BusinessToolRepository(db)
            return await repository.list_available_project_app_tools(
                project_app_id=int(project_app_id)
            )

    async def list_available_operations(
        self,
        project_app_id: int | None,
    ) -> list[BusinessOperationDefinition]:
        records = await self.list_available_tools(project_app_id)
        return self.registry.list_from_records(records)

    async def execute(self, request: BusinessOperationRequest) -> BusinessOperationResult:
        project_app_id = request.project_app_id or request.scope.get("project_app_id")
        record = await self._get_available_tool(
            project_app_id=project_app_id,
            operation_id=request.operation_id,
        )
        if record is None:
            return BusinessOperationResult(
                success=False,
                operation_id=request.operation_id,
                message="当前应用端未授权该业务工具，或工具尚未发布。",
                error=BusinessOperationErrorPayload(
                    code="TOOL_NOT_AVAILABLE",
                    message="当前应用端未授权该业务工具，或工具尚未发布。",
                ),
            )

        operation = self.registry.from_tool_record(record)
        missing_fields = self._collect_missing_fields(operation, request)
        if missing_fields:
            return BusinessOperationResult(
                success=False,
                operation_id=operation.id,
                message="还需要补充必要信息。",
                missing_fields=missing_fields,
                error=BusinessOperationErrorPayload(
                    code="MISSING_PARAMS",
                    message="还需要补充必要信息。",
                    retryable=True,
                ),
            )

        invalid_params = self._collect_invalid_params(operation, request)
        if invalid_params:
            message = f"以下参数类型不正确：{'、'.join(invalid_params)}。"
            return BusinessOperationResult(
                success=False,
                operation_id=operation.id,
                message=message,
                error=BusinessOperationErrorPayload(
                    code="INVALID_PARAMS",
                    message=message,
                    retryable=True,
                ),
            )

        if operation.requires_confirmation and request.scope.get("confirmed") is not True:
            return BusinessOperationResult(
                success=False,
                operation_id=operation.id,
                message=f"业务工具“{operation.name}”需要用户确认后才能执行。",
                error=BusinessOperationErrorPayload(
                    code="CONFIRMATION_REQUIRED",
                    message=f"业务工具“{operation.name}”需要用户确认后才能执行。",
                    retryable=True,
                ),
            )

        return await self.http_tool_gateway.execute(
            operation=operation,
            tool=record.tool,
            implementation=record.implementation,
            api=record.api,
            connection=record.connection,
            request=request,
        )

    async def _get_available_tool(
        self,
        *,
        project_app_id: int | str | None,
        operation_id: str,
    ) -> BusinessToolExecutionRecord | None:
        if project_app_id is None:
            return None
        async with AsyncSessionLocal() as db:
            repository = BusinessToolRepository(db)
            return await repository.get_available_project_app_tool_by_key(
                project_app_id=int(project_app_id),
                tool_key=operation_id,
            )

    @staticmethod
    def _is_blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    def _collect_missing_fields(
        self,
        operation: BusinessOperationDefinition,
        request: BusinessOperationRequest,
    ) -> list[BusinessOperationMissingField]:
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

    def _collect_invalid_params(
        self,
        operation: BusinessOperationDefinition,
        request: BusinessOperationRequest,
    ) -> list[str]:
        invalid: list[str] = []
        for param in operation.params:
            value = request.params.get(param.key)
            if self._is_blank(value):
                continue
            is_valid = (
                isinstance(value, str)
                if param.type in {"text", "select"}
                else isinstance(value, (int, float)) and not isinstance(value, bool)
                if param.type == "number"
                else isinstance(value, bool)
                if param.type == "boolean"
                else isinstance(value, list)
                if param.type == "array"
                else isinstance(value, dict)
            )
            if not is_valid:
                invalid.append(param.label)
        return invalid
