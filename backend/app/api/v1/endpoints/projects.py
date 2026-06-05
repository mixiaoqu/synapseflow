"""Project and project application management endpoints."""

from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.application.project_service import ProjectService
from app.core.config import settings
from app.core.security import create_embed_token
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.project import (
    EmbedSessionResponse,
    ProjectAppCreate,
    ProjectAppListResponse,
    ProjectAppResponse,
    ProjectAppUpdate,
    ProjectCopy,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter()


def _resolve_embed_frontend_base_url(request: Request) -> str:
    configured = settings.EMBED_FRONTEND_BASE_URL.strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    team_id: int | None = Query(None),
    keyword: str | None = Query(None),
    status: str = Query("all", pattern="^(all|active|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).list_projects_page(
        team_id=team_id,
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
    return await ProjectService(db, user_id=current_user.id).create_project(body)


@router.post("/{project_id}/copy", response_model=ProjectResponse)
async def copy_project(
    project_id: int,
    body: ProjectCopy,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).copy_project(
        project_id=project_id,
        payload=body,
    )


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


@router.get("/{project_id}/apps", response_model=ProjectAppListResponse)
async def list_project_apps(
    project_id: int,
    keyword: str | None = Query(None),
    status: str = Query("all", pattern="^(all|active|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await ProjectService(db, user_id=current_user.id).list_apps_page(
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


@router.post("/{project_id}/apps/{app_id}/embed-preview", response_model=EmbedSessionResponse)
async def create_project_app_embed_preview(
    project_id: int,
    app_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    runtime = await ProjectService(db, user_id=current_user.id).get_app_runtime(
        project_id=project_id,
        app_id=app_id,
        active_only=True,
    )
    expires = max(1, settings.EMBED_TOKEN_EXPIRE_MINUTES)
    token = create_embed_token(
        project_id=runtime.project.id,
        project_app_id=runtime.app.id,
        external_user_id=f"admin-preview:{current_user.id}",
        external_user_name=(current_user.full_name or current_user.username or "").strip() or None,
        expires_delta=timedelta(minutes=expires),
    )
    base_url = _resolve_embed_frontend_base_url(request)
    embed_url = f"{base_url}/embed/assistant?{urlencode({'token': token})}"
    return EmbedSessionResponse(
        embed_url=embed_url,
        expires_in_seconds=expires * 60,
    )
