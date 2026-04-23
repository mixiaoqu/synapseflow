"""Project and project application management endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.application.project_service import ProjectService
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.project import (
    ProjectAppCreate,
    ProjectAppResponse,
    ProjectAppUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter()


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    team_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).list_projects(team_id=team_id)


@router.post("", response_model=ProjectResponse)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).create_project(body)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).get_project(project_id)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).update_project(project_id, body)


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await ProjectService(db, user_id=current_user.id).delete_project(project_id)
    return {"message": "Deleted successfully"}


@router.get("/{project_id}/apps", response_model=list[ProjectAppResponse])
async def list_project_apps(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).list_apps(project_id=project_id)


@router.post("/{project_id}/apps", response_model=ProjectAppResponse)
async def create_project_app(
    project_id: int,
    body: ProjectAppCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).create_app(
        project_id=project_id,
        payload=body,
    )


@router.get("/{project_id}/apps/{app_id}", response_model=ProjectAppResponse)
async def get_project_app(
    project_id: int,
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).get_app(
        project_id=project_id,
        app_id=app_id,
    )


@router.put("/{project_id}/apps/{app_id}", response_model=ProjectAppResponse)
async def update_project_app(
    project_id: int,
    app_id: int,
    body: ProjectAppUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).update_app(
        project_id=project_id,
        app_id=app_id,
        payload=body,
    )


@router.delete("/{project_id}/apps/{app_id}")
async def delete_project_app(
    project_id: int,
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await ProjectService(db, user_id=current_user.id).delete_app(
        project_id=project_id,
        app_id=app_id,
    )
    return {"message": "Deleted successfully"}
