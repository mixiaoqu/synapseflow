"""Team management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, require_system_admin
from app.application.permission_service import PermissionService
from app.core.authz import (
    PERMISSION_DELETE_TEAM,
    PERMISSION_MANAGE_TEAM_MEMBER,
    PERMISSION_VIEW_TEAM_RESOURCE,
)
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.team import (
    TeamBulkActionRequest,
    TeamBulkActionResponse,
    TeamCreate,
    TeamListResponse,
    TeamMemberBulkDelete,
    TeamMemberBulkRoleUpdate,
    TeamMemberCreate,
    TeamMemberResponse,
    TeamMemberUpdate,
    TeamOptionResponse,
    TeamResponse,
    TeamUpdate,
)
from app.repositories.team_repository import TeamRepository

router = APIRouter()


@router.get("", response_model=TeamListResponse)
async def list_teams(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    keyword: str | None = Query(None, description="搜索关键词，匹配名称或编码"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页查询团队列表，支持按名称/编码模糊搜索。"""
    permission_service = PermissionService(db)
    accessible_team_ids = await permission_service.list_accessible_team_ids(current_user)
    repo = TeamRepository(db, user_id=current_user.id)
    rows, total = await repo.list_teams_paginated(
        page=page, page_size=page_size, keyword=keyword, team_ids=accessible_team_ids
    )
    return TeamListResponse(
        items=rows,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/options", response_model=list[TeamOptionResponse])
async def list_team_options(
    keyword: str | None = Query(None, description="搜索关键词，匹配名称或编码"),
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
    include_team_id: int | None = Query(None, description="确保包含的当前团队 ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    accessible_team_ids = await permission_service.list_accessible_team_ids(current_user)
    repo = TeamRepository(db, user_id=current_user.id)
    return await repo.list_team_options(
        keyword=keyword,
        limit=limit,
        team_ids=accessible_team_ids,
        include_team_id=include_team_id,
    )


@router.post("", response_model=TeamResponse)
async def create_team(
    body: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    repo = TeamRepository(db, user_id=current_user.id)
    if await repo.is_code_taken(body.code):
        raise HTTPException(status_code=409, detail="团队编码已存在")
    return await repo.create_team(
        name=body.name,
        code=body.code,
        description=body.description,
        member_ids=body.member_ids,
    )


@router.post("/bulk-actions", response_model=TeamBulkActionResponse)
async def bulk_action_teams(
    body: TeamBulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    repo = TeamRepository(db, user_id=current_user.id)
    if body.action == "delete":
        for team_id in body.team_ids:
            if not await permission_service.has_team_permission(
                current_user, team_id, PERMISSION_DELETE_TEAM
            ):
                raise HTTPException(status_code=403, detail="Team delete permission denied")
        affected = await repo.delete_teams(body.team_ids)
        return TeamBulkActionResponse(affected=affected)
    raise HTTPException(status_code=400, detail="不支持的批量操作")


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int,
    body: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    if not await permission_service.has_team_permission(
        current_user, team_id, PERMISSION_VIEW_TEAM_RESOURCE
    ):
        raise HTTPException(status_code=403, detail="Team access denied")
    repo = TeamRepository(db, user_id=current_user.id)
    if await repo.is_code_taken(body.code, exclude_team_id=team_id):
        raise HTTPException(status_code=409, detail="团队编码已存在")
    team = await repo.update_team(
        team_id,
        name=body.name,
        code=body.code,
        description=body.description,
    )
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.delete("/{team_id}")
async def delete_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    if not await permission_service.has_team_permission(
        current_user, team_id, PERMISSION_DELETE_TEAM
    ):
        raise HTTPException(status_code=403, detail="Team delete permission denied")
    repo = TeamRepository(db, user_id=current_user.id)
    ok = await repo.delete_team(team_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"message": "Deleted successfully"}


@router.get("/{team_id}/members", response_model=list[TeamMemberResponse])
async def list_team_members(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    if not await permission_service.has_team_permission(
        current_user, team_id, PERMISSION_MANAGE_TEAM_MEMBER
    ):
        raise HTTPException(status_code=403, detail="Team member permission denied")
    repo = TeamRepository(db, user_id=current_user.id)
    team = await repo.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return await repo.list_members(team_id)


@router.post("/{team_id}/members", response_model=TeamMemberResponse)
async def add_team_member(
    team_id: int,
    body: TeamMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    if not await permission_service.has_team_permission(
        current_user, team_id, PERMISSION_MANAGE_TEAM_MEMBER
    ):
        raise HTTPException(status_code=403, detail="Team member permission denied")
    repo = TeamRepository(db, user_id=current_user.id)
    team = await repo.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    member = await repo.add_member(team_id, user_id=body.user_id, role=body.role)
    if not member:
        raise HTTPException(status_code=404, detail="Team not found")
    return member


@router.put("/{team_id}/members/{user_id}", response_model=TeamMemberResponse)
async def update_team_member(
    team_id: int,
    user_id: int,
    body: TeamMemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    if not await permission_service.has_team_permission(
        current_user, team_id, PERMISSION_MANAGE_TEAM_MEMBER
    ):
        raise HTTPException(status_code=403, detail="Team member permission denied")
    repo = TeamRepository(db, user_id=current_user.id)
    member = await repo.update_member(team_id, user_id=user_id, role=body.role)
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    return member


@router.post("/{team_id}/members/bulk-role", response_model=TeamBulkActionResponse)
async def bulk_update_team_member_role(
    team_id: int,
    body: TeamMemberBulkRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    if not await permission_service.has_team_permission(
        current_user, team_id, PERMISSION_MANAGE_TEAM_MEMBER
    ):
        raise HTTPException(status_code=403, detail="Team member permission denied")
    repo = TeamRepository(db, user_id=current_user.id)
    affected = await repo.update_members_role(team_id, user_ids=body.user_ids, role=body.role)
    if affected == 0 and not await repo.get_team(team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamBulkActionResponse(affected=affected)


@router.post("/{team_id}/members/bulk-delete", response_model=TeamBulkActionResponse)
async def bulk_delete_team_members(
    team_id: int,
    body: TeamMemberBulkDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    if not await permission_service.has_team_permission(
        current_user, team_id, PERMISSION_MANAGE_TEAM_MEMBER
    ):
        raise HTTPException(status_code=403, detail="Team update permission denied")
    repo = TeamRepository(db, user_id=current_user.id)
    affected = await repo.delete_members(team_id, user_ids=body.user_ids)
    if affected == 0 and not await repo.get_team(team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamBulkActionResponse(affected=affected)


@router.delete("/{team_id}/members/{user_id}")
async def delete_team_member(
    team_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    if not await permission_service.has_team_permission(
        current_user, team_id, PERMISSION_MANAGE_TEAM_MEMBER
    ):
        raise HTTPException(status_code=403, detail="Team member permission denied")
    repo = TeamRepository(db, user_id=current_user.id)
    ok = await repo.delete_member(team_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Team member not found")
    return {"message": "Deleted successfully"}
