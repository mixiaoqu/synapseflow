"""Product management endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.application.product_service import ProductService
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.product import ProductCreate, ProductListResponse, ProductResponse, ProductUpdate

router = APIRouter()


@router.get("", response_model=ProductListResponse)
async def list_products(
    team_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProductService(db, user_id=current_user.id).list_products_page(
        team_id=team_id,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ProductResponse)
async def create_product(
    body: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProductService(db, user_id=current_user.id).create_product(body)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProductService(db, user_id=current_user.id).get_product(product_id)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProductService(db, user_id=current_user.id).update_product(product_id, body)


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await ProductService(db, user_id=current_user.id).delete_product(product_id)
    return {"message": "Deleted successfully"}
