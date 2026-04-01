"""Team management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.team import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberResponse,
    TeamMemberUpdate,
    TeamResponse,
    TeamUpdate,
)
from app.repositories.team_repository import TeamRepository

router = APIRouter()


@router.get("", response_model=list[TeamResponse])
async def list_teams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = TeamRepository(db, user_id=current_user.id)
    return await repo.list_teams()


@router.post("", response_model=TeamResponse)
async def create_team(
    body: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = TeamRepository(db, user_id=current_user.id)
    return await repo.create_team(
        name=body.name,
        code=body.code,
        description=body.description,
    )


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int,
    body: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = TeamRepository(db, user_id=current_user.id)
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
    repo = TeamRepository(db, user_id=current_user.id)
    member = await repo.update_member(team_id, user_id=user_id, role=body.role)
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    return member


@router.delete("/{team_id}/members/{user_id}")
async def delete_team_member(
    team_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = TeamRepository(db, user_id=current_user.id)
    ok = await repo.delete_member(team_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Team member not found")
    return {"message": "Deleted successfully"}
