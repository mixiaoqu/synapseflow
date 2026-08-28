"""Project and project application management endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.application.project_service import ProjectService
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.project import (
    ProjectAppBulkActionRequest,
    ProjectAppBulkActionResponse,
    ProjectAppCreate,
    ProjectAppListResponse,
    ProjectAppResponse,
    ProjectAppUpdate,
    ProjectBulkActionRequest,
    ProjectBulkActionResponse,
    ProjectCopy,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter()


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    team_id: int | None = Query(None),
    product_id: int | None = Query(None),
    keyword: str | None = Query(None),
    status: str = Query("all", pattern="^(all|active|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id, user=current_user).list_projects_page(
        team_id=team_id,
        product_id=product_id,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ProjectResponse)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id, user=current_user).create_project(body)


@router.post("/{project_id}/copy", response_model=ProjectResponse)
async def copy_project(
    project_id: int,
    body: ProjectCopy,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id, user=current_user).copy_project(
        project_id=project_id,
        payload=body,
    )


@router.post("/bulk-action", response_model=ProjectBulkActionResponse)
async def bulk_action_projects(
    body: ProjectBulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id, user=current_user).bulk_action_projects(body)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id, user=current_user).get_project(project_id)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id, user=current_user).update_project(project_id, body)


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await ProjectService(db, user_id=current_user.id, user=current_user).delete_project(project_id)
    return {"message": "Deleted successfully"}


@router.get("/{project_id}/apps", response_model=ProjectAppListResponse)
async def list_project_apps(
    project_id: int,
    keyword: str | None = Query(None),
    status: str = Query("all", pattern="^(all|active|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id, user=current_user).list_apps_page(
        project_id=project_id,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("/{project_id}/apps", response_model=ProjectAppResponse)
async def create_project_app(
    project_id: int,
    body: ProjectAppCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id, user=current_user).create_app(
        project_id=project_id,
        payload=body,
    )


@router.post("/{project_id}/apps/bulk-action", response_model=ProjectAppBulkActionResponse)
async def bulk_action_project_apps(
    project_id: int,
    body: ProjectAppBulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id, user=current_user).bulk_action_apps(
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
    return await ProjectService(db, user_id=current_user.id, user=current_user).get_app(
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
    return await ProjectService(db, user_id=current_user.id, user=current_user).update_app(
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
    await ProjectService(db, user_id=current_user.id, user=current_user).delete_app(
        project_id=project_id,
        app_id=app_id,
    )
    return {"message": "Deleted successfully"}
