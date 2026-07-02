"""Application service for controlled business data operations."""

from __future__ import annotations

from typing import Any

from app.application.business_operations.mock_gateway import MockBusinessGateway
from app.application.business_operations.registry import (
    PRODUCT_SEARCH_OPERATION_ID,
    BusinessOperationRegistry,
)
from app.application.business_operations.schemas import (
    BusinessOperationDefinition,
    BusinessOperationErrorPayload,
    BusinessOperationMissingField,
    BusinessOperationRequest,
    BusinessOperationResult,
)


class BusinessOperationService:
    """Validates and executes whitelisted business data operations."""

    def __init__(
        self,
        *,
        registry: BusinessOperationRegistry | None = None,
        gateway: MockBusinessGateway | None = None,
    ) -> None:
        self.registry = registry or BusinessOperationRegistry()
        self.gateway = gateway or MockBusinessGateway()

    async def execute(self, request: BusinessOperationRequest) -> BusinessOperationResult:
        operation = self.registry.get(request.operation_id)
        if operation is None:
            return BusinessOperationResult(
                success=False,
                operation_id=request.operation_id,
                message="不支持该业务操作。",
                error=BusinessOperationErrorPayload(
                    code="UNSUPPORTED_OPERATION",
                    message="不支持该业务操作。",
                ),
            )

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

        if operation.id == PRODUCT_SEARCH_OPERATION_ID:
            return await self._search_products(operation, request)

        return BusinessOperationResult(
            success=False,
            operation_id=operation.id,
            message="该业务操作暂未接入执行器。",
            error=BusinessOperationErrorPayload(
                code="EXECUTOR_NOT_FOUND",
                message="该业务操作暂未接入执行器。",
            ),
        )

    @staticmethod
    def _is_blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    def _collect_missing_fields(
        self,
        operation: BusinessOperationDefinition,
        request: BusinessOperationRequest,
    ) -> list[BusinessOperationMissingField]:
        missing_fields: list[BusinessOperationMissingField] = []
        for scope_key in operation.required_scope:
            if self._is_blank(request.scope.get(scope_key)):
                missing_fields.append(
                    BusinessOperationMissingField(
                        key=scope_key,
                        label="门店 ID" if scope_key == "store_id" else scope_key,
                        type="text",
                        required=True,
                        description="业务作用域缺少必要信息。",
                    )
                )

        for param in operation.params:
            if param.required and self._is_blank(request.params.get(param.key)):
                missing_fields.append(
                    BusinessOperationMissingField(
                        key=param.key,
                        label=param.label,
                        type=param.type,
                        required=param.required,
                        description=param.description,
                        resolver=param.resolver,
                    )
                )
        return missing_fields

    async def _search_products(
        self,
        operation: BusinessOperationDefinition,
        request: BusinessOperationRequest,
    ) -> BusinessOperationResult:
        store_id = str(request.scope["store_id"]).strip()
        keyword = str(request.params["keyword"]).strip()
        products = await self.gateway.search_products(
            store_id=store_id,
            keyword=keyword,
        )
        product_payload = [product.model_dump() for product in products]
        if not products:
            return BusinessOperationResult(
                success=True,
                operation_id=operation.id,
                message=f"门店 {store_id} 未找到与“{keyword}”相关的商品。",
                data={
                    "store_id": store_id,
                    "keyword": keyword,
                    "items": [],
                    "total": 0,
                },
            )

        return BusinessOperationResult(
            success=True,
            operation_id=operation.id,
            message=f"门店 {store_id} 找到 {len(products)} 个与“{keyword}”相关的商品。",
            data={
                "store_id": store_id,
                "keyword": keyword,
                "items": product_payload,
                "total": len(product_payload),
            },
        )
