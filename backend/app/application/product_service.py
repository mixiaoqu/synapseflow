"""Product application service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product
from app.models.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.repositories.product_repository import ProductRecord, ProductRepository
from app.repositories.team_repository import TeamRepository


class ProductService:
    def __init__(self, db: AsyncSession, *, user_id: int):
        self.db = db
        self.user_id = user_id
        self.repository = ProductRepository(db)
        self.team_repository = TeamRepository(db, user_id=user_id)

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

    async def _ensure_team_access(self, team_id: int) -> None:
        if not await self.team_repository.can_access_team(team_id):
            raise HTTPException(status_code=403, detail="Team access denied")

    async def list_products(self, *, team_id: int | None = None) -> list[ProductResponse]:
        if team_id is not None:
            await self._ensure_team_access(team_id)
        records = await self.repository.list_products(team_id=team_id)
        return [self._to_response(record) for record in records]

    async def get_product(self, product_id: int) -> ProductResponse:
        record = await self.repository.get_product_record(product_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Product not found")
        await self._ensure_team_access(record.product.team_id)
        return self._to_response(record)

    async def create_product(self, payload: ProductCreate) -> ProductResponse:
        await self._ensure_team_access(payload.team_id)
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
        await self._ensure_team_access(product.team_id)
        await self._ensure_team_access(payload.team_id)
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
        await self._ensure_team_access(product.team_id)
        await self.repository.delete_product(product)
