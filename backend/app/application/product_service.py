"""Product application service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.permission_service import PermissionService
from app.core.authz import PERMISSION_MANAGE_PROJECT, PERMISSION_VIEW_TEAM_RESOURCE
from app.db.models import Product
from app.db.models import User
from app.models.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.repositories.product_repository import ProductRecord, ProductRepository


class ProductService:
    def __init__(self, db: AsyncSession, *, user_id: int, user: User | None = None):
        self.db = db
        self.user_id = user_id
        self.user = user
        self.repository = ProductRepository(db)
        self.permission_service = PermissionService(db)

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None

    @staticmethod
    def _normalize_code(value: str) -> str:
        code = ProductRepository.normalize_code(value)
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        return code

    @staticmethod
    def _to_response(record: ProductRecord) -> ProductResponse:
        product = record.product
        return ProductResponse(
            id=product.id,
            team_id=product.team_id,
            team_name=record.team_name,
            code=product.code,
            name=product.name,
            description=product.description,
            is_active=product.is_active,
            project_count=record.project_count,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

    async def _ensure_team_permission(
        self,
        team_id: int,
        permission: str = PERMISSION_VIEW_TEAM_RESOURCE,
    ) -> None:
        if self.user is None:
            raise HTTPException(status_code=403, detail="Team access denied")
        if permission == PERMISSION_VIEW_TEAM_RESOURCE:
            allowed = await self.permission_service.can_access_team(self.user, team_id)
        else:
            allowed = await self.permission_service.has_team_permission(
                self.user, team_id, permission
            )
        if not allowed:
            raise HTTPException(status_code=403, detail="Team access denied")

    async def list_products(self, *, team_id: int | None = None) -> list[ProductResponse]:
        if team_id is not None:
            await self._ensure_team_permission(team_id)
        records = await self.repository.list_products(team_id=team_id)
        return [self._to_response(record) for record in records]

    async def list_products_page(
        self,
        *,
        team_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> ProductListResponse:
        if team_id is not None:
            await self._ensure_team_permission(team_id)
        normalized_page = max(1, int(page))
        normalized_page_size = min(100, max(1, int(page_size)))
        total = await self.repository.count_products(team_id=team_id)
        records = await self.repository.list_products_page(
            team_id=team_id,
            offset=(normalized_page - 1) * normalized_page_size,
            limit=normalized_page_size,
        )
        return ProductListResponse(
            items=[self._to_response(record) for record in records],
            total=total,
            page=normalized_page,
            page_size=normalized_page_size,
        )

    async def get_product(self, product_id: int) -> ProductResponse:
        record = await self.repository.get_product_record(product_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Product not found")
        await self._ensure_team_permission(record.product.team_id)
        return self._to_response(record)

    async def create_product(self, payload: ProductCreate) -> ProductResponse:
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        code = self._normalize_code(payload.code)
        if await self.repository.product_code_exists(code):
            raise HTTPException(status_code=400, detail="Product code already exists")
        product = Product(
            team_id=payload.team_id,
            code=code,
            name=payload.name.strip(),
            description=self._normalize_optional_text(payload.description),
            is_active=payload.is_active,
        )
        await self.repository.create_product(product)
        record = await self.repository.get_product_record(product.id)
        if record is None:
            raise HTTPException(status_code=500, detail="Product creation failed")
        return self._to_response(record)

    async def update_product(self, product_id: int, payload: ProductUpdate) -> ProductResponse:
        product = await self.repository.get_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        await self._ensure_team_permission(product.team_id, PERMISSION_MANAGE_PROJECT)
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        code = self._normalize_code(payload.code)
        if await self.repository.product_code_exists(code, exclude_id=product_id):
            raise HTTPException(status_code=400, detail="Product code already exists")
        product.team_id = payload.team_id
        product.code = code
        product.name = payload.name.strip()
        product.description = self._normalize_optional_text(payload.description)
        product.is_active = payload.is_active
        await self.repository.update_product(product)
        record = await self.repository.get_product_record(product.id)
        if record is None:
            raise HTTPException(status_code=500, detail="Product update failed")
        return self._to_response(record)

    async def delete_product(self, product_id: int) -> None:
        product = await self.repository.get_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        await self._ensure_team_permission(product.team_id, PERMISSION_MANAGE_PROJECT)
        await self.repository.delete_product(product)
