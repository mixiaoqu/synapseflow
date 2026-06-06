"""Admin user management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_any_admin_role
from app.core.authz import ROLE_KB_ADMIN, normalize_role
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.user_admin import (
    AdminUserBulkAction,
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    UserListResponse,
)
from app.repositories.user_repository import UserRepository

router = APIRouter()


def _to_user_response(user: User, team_memberships: list[dict] | None = None) -> AdminUserResponse:
    memberships = team_memberships or []
    names = [item["team_name"] for item in memberships]
    return AdminUserResponse.model_validate(user).model_copy(
        update={
            "team_names": names,
            "team_count": len(names),
            "team_memberships": memberships,
        }
    )


async def _ensure_user_update_allowed(
    repo: UserRepository,
    *,
    current_user: User,
    target_user: User,
    role: str | None = None,
    is_active: bool | None = None,
) -> None:
    if target_user.id == current_user.id and is_active is False:
        raise HTTPException(status_code=400, detail="不能停用当前登录账号")
    if target_user.id == current_user.id and role is not None and normalize_role(role) != normalize_role(target_user.role):
        raise HTTPException(status_code=400, detail="不能修改当前登录账号的角色")

    is_admin = normalize_role(target_user.role) == ROLE_KB_ADMIN
    will_stop_being_active_admin = (
        is_admin
        and (
            is_active is False
            or (role is not None and normalize_role(role) != ROLE_KB_ADMIN)
        )
    )
    if will_stop_being_active_admin and await repo.count_active_admins() <= 1:
        raise HTTPException(status_code=400, detail="不能停用或降权最后一个启用中的管理员")


async def _ensure_user_delete_allowed(
    repo: UserRepository,
    *,
    current_user: User,
    target_user: User,
) -> None:
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    if normalize_role(target_user.role) == ROLE_KB_ADMIN and await repo.count_active_admins() <= 1:
        raise HTTPException(status_code=400, detail="不能删除最后一个启用中的管理员")


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    keyword: str | None = Query(None, description="搜索关键词，匹配用户名、邮箱或姓名"),
    role: str | None = Query(None, description="角色筛选"),
    is_active: bool | None = Query(None, description="启用状态筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    del current_user
    repo = UserRepository(db)
    rows, total = await repo.list_users_paginated(
        page=page,
        page_size=page_size,
        keyword=keyword,
        role=role,
        is_active=is_active,
    )
    team_memberships = await repo.get_user_team_memberships([user.id for user in rows])
    return UserListResponse(
        items=[_to_user_response(user, team_memberships.get(user.id)) for user in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    repo = UserRepository(db)
    if await repo.get_by_username(body.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    if await repo.get_by_email(body.email):
        raise HTTPException(status_code=409, detail="邮箱已存在")
    created = await repo.create_user(
        username=body.username,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
    )
    return _to_user_response(created, [])


@router.post("/bulk-action")
async def bulk_action_users(
    body: AdminUserBulkAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    repo = UserRepository(db)
    user_ids = list(dict.fromkeys(body.user_ids))
    targets = [user for user_id in user_ids if (user := await repo.get_by_id(user_id)) is not None]
    if not targets:
        raise HTTPException(status_code=404, detail="未找到可操作的用户")

    if body.action == "delete":
        for target in targets:
            await _ensure_user_delete_allowed(repo, current_user=current_user, target_user=target)
        deleted = await repo.soft_delete_users([user.id for user in targets])
        return {"message": "Deleted successfully", "affected": len(deleted)}

    target_active = body.action == "enable"
    for target in targets:
        await _ensure_user_update_allowed(
            repo,
            current_user=current_user,
            target_user=target,
            is_active=target_active,
        )
        await repo.update_user(target.id, is_active=target_active)
    return {"message": "Updated successfully", "affected": len(targets)}


@router.get("/{user_id}", response_model=AdminUserResponse)
async def get_user_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    del current_user
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    team_memberships = await repo.get_user_team_memberships([user.id])
    return _to_user_response(user, team_memberships.get(user.id))


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    body: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    repo = UserRepository(db)
    existing = await repo.get_by_id(user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    await _ensure_user_update_allowed(
        repo,
        current_user=current_user,
        target_user=existing,
        role=body.role,
        is_active=body.is_active,
    )

    if body.username is not None:
        duplicate = await repo.get_by_username(body.username)
        if duplicate and duplicate.id != user_id:
            raise HTTPException(status_code=409, detail="用户名已存在")
    if body.email is not None:
        duplicate = await repo.get_by_email(body.email)
        if duplicate and duplicate.id != user_id:
            raise HTTPException(status_code=409, detail="邮箱已存在")

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
        raise HTTPException(status_code=404, detail="用户不存在")
    team_memberships = await repo.get_user_team_memberships([updated.id])
    return _to_user_response(updated, team_memberships.get(updated.id))


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    repo = UserRepository(db)
    existing = await repo.get_by_id(user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    await _ensure_user_delete_allowed(repo, current_user=current_user, target_user=existing)
    deleted = await repo.soft_delete_user(user_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "Deleted successfully"}
