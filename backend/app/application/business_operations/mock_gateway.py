"""Local mock gateway that mimics external business data APIs."""

from __future__ import annotations

from app.application.business_operations.schemas import ProductSearchItem


class MockBusinessGateway:
    """In-memory stand-in for future external business APIs."""

    _products = [
        ProductSearchItem(
            store_id="store_1001",
            sku_id="sku_001",
            name="可口可乐 500ml",
            barcode="690000000001",
            category="饮料",
            price=3.5,
            stock=120,
            unit="瓶",
        ),
        ProductSearchItem(
            store_id="store_1001",
            sku_id="sku_002",
            name="百事可乐 500ml",
            barcode="690000000002",
            category="饮料",
            price=3.3,
            stock=86,
            unit="瓶",
        ),
        ProductSearchItem(
            store_id="store_1001",
            sku_id="sku_003",
            name="农夫山泉 550ml",
            barcode="690000000003",
            category="饮料",
            price=2.0,
            stock=240,
            unit="瓶",
        ),
        ProductSearchItem(
            store_id="store_1002",
            sku_id="sku_001",
            name="可口可乐 500ml",
            barcode="690000000001",
            category="饮料",
            price=3.8,
            stock=45,
            unit="瓶",
        ),
        ProductSearchItem(
            store_id="store_1002",
            sku_id="sku_004",
            name="统一冰红茶 500ml",
            barcode="690000000004",
            category="饮料",
            price=3.0,
            stock=67,
            unit="瓶",
        ),
    ]

    async def search_products(
        self,
        *,
        store_id: str,
        keyword: str,
        limit: int = 10,
    ) -> list[ProductSearchItem]:
        normalized_store_id = store_id.strip()
        normalized_keyword = keyword.strip().lower()
        if not normalized_store_id or not normalized_keyword:
            return []

        matched: list[ProductSearchItem] = []
        for product in self._products:
            if product.store_id != normalized_store_id:
                continue
            searchable_text = " ".join(
                value
                for value in [
                    product.sku_id,
                    product.name,
                    product.barcode or "",
                    product.category or "",
                ]
                if value
            ).lower()
            if normalized_keyword in searchable_text:
                matched.append(product)
            if len(matched) >= limit:
                break
        return matched
