"""Admin user management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_any_admin_role
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.user_admin import AdminUserCreate, AdminUserResponse, AdminUserUpdate
from app.repositories.user_repository import UserRepository

router = APIRouter()


@router.get("", response_model=list[AdminUserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    del current_user
    return await UserRepository(db).list_users()


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
