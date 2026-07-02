"""Whitelist registry for controlled business data operations."""

from __future__ import annotations

from app.application.business_operations.schemas import (
    BusinessOperationDefinition,
    BusinessOperationParamSpec,
)

PRODUCT_SEARCH_OPERATION_ID = "product.search"


class BusinessOperationRegistry:
    """Holds the business data operations an agent is allowed to request."""

    def __init__(self) -> None:
        self._operations = {
            PRODUCT_SEARCH_OPERATION_ID: BusinessOperationDefinition(
                id=PRODUCT_SEARCH_OPERATION_ID,
                name="查询商品数据",
                description="按门店和关键词查询商品库存与价格。",
                risk_level="low",
                requires_confirmation=False,
                required_scope=["store_id"],
                params=[
                    BusinessOperationParamSpec(
                        key="keyword",
                        label="查询关键词",
                        type="text",
                        required=True,
                        description="商品名称、条码或 SKU 编码。",
                    )
                ],
            )
        }

    def list_operations(self) -> list[BusinessOperationDefinition]:
        return list(self._operations.values())

    def get(self, operation_id: str) -> BusinessOperationDefinition | None:
        return self._operations.get(operation_id)
