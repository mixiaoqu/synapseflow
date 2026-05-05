"""Product persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product, Project, Team


@dataclass(slots=True)
class ProductRecord:
    product: Product
    team_name: str | None
    project_count: int


class ProductRepository:
    """Persist products."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def normalize_code(code: str) -> str:
        return (code or "").strip().lower()

    async def list_products(self, *, team_id: int | None = None) -> list[ProductRecord]:
        project_count = func.count(Project.id)
        stmt = (
            select(Product, Team.name, project_count.label("project_count"))
            .join(Team, Team.id == Product.team_id)
            .outerjoin(Project, Project.product_id == Product.id)
            .group_by(Product.id, Team.name)
            .order_by(Product.created_at.desc(), Product.id.desc())
        )
        if team_id is not None:
            stmt = stmt.where(Product.team_id == team_id)
        rows = (await self.db.execute(stmt)).all()
        return [
            ProductRecord(product=product, team_name=team_name, project_count=int(count or 0))
            for product, team_name, count in rows
        ]

    async def get_product_record(self, product_id: int) -> ProductRecord | None:
        project_count = func.count(Project.id)
        stmt = (
            select(Product, Team.name, project_count.label("project_count"))
            .join(Team, Team.id == Product.team_id)
            .outerjoin(Project, Project.product_id == Product.id)
            .where(Product.id == product_id)
            .group_by(Product.id, Team.name)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        product, team_name, count = row
        return ProductRecord(product=product, team_name=team_name, project_count=int(count or 0))

    async def get_product(self, product_id: int) -> Product | None:
        return await self.db.get(Product, product_id)

    async def get_product_by_code(self, code: str) -> Product | None:
        stmt = select(Product).where(Product.code == self.normalize_code(code))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def product_code_exists(self, code: str, *, exclude_id: int | None = None) -> bool:
        stmt = select(func.count()).select_from(Product).where(Product.code == self.normalize_code(code))
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        return bool((await self.db.execute(stmt)).scalar() or 0)

    async def create_product(self, product: Product) -> Product:
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def update_product(self, product: Product) -> Product:
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def delete_product(self, product: Product) -> None:
        await self.db.delete(product)
        await self.db.commit()
