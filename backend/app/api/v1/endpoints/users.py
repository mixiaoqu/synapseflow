"""Admin user management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_any_admin_role
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.user_admin import AdminUserCreate, AdminUserResponse, AdminUserUpdate, UserListResponse
from app.repositories.user_repository import UserRepository

router = APIRouter()


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    keyword: str | None = Query(None, description="搜索关键词，匹配用户名、邮箱或姓名"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    del current_user
    repo = UserRepository(db)
    rows, total = await repo.list_users_paginated(page=page, page_size=page_size, keyword=keyword)
    return UserListResponse(items=rows, total=total, page=page, page_size=page_size)


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    del current_user
    repo = UserRepository(db)
    if await repo.get_by_username(body.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    if await repo.get_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already exists")
    return await repo.create_user(
        username=body.username,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
    )


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    body: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    del current_user
    repo = UserRepository(db)
    existing = await repo.get_by_id(user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.username is not None:
        duplicate = await repo.get_by_username(body.username)
        if duplicate and duplicate.id != user_id:
            raise HTTPException(status_code=409, detail="Username already exists")
    if body.email is not None:
        duplicate = await repo.get_by_email(body.email)
        if duplicate and duplicate.id != user_id:
            raise HTTPException(status_code=409, detail="Email already exists")

    updated = await repo.update_user(
        user_id,
        username=body.username,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated
