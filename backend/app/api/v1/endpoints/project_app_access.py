"""Project application server-to-server access endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.application.project_app_access_service import ProjectAppAccessService
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.project_app_access import (
    ProjectAppAccessCreate,
    ProjectAppAccessIssuedResponse,
    ProjectAppAccessResponse,
    ProjectAppAccessUpdate,
)

router = APIRouter()


def _response(credential) -> ProjectAppAccessResponse:
    return ProjectAppAccessResponse.model_validate(credential)


def _issued_response(issued) -> ProjectAppAccessIssuedResponse:
    return ProjectAppAccessIssuedResponse(
        **ProjectAppAccessResponse.model_validate(issued.credential).model_dump(),
        client_secret=issued.client_secret,
    )


@router.get("/project-apps/{project_id}/{app_id}/access", response_model=ProjectAppAccessResponse)
async def get_project_app_access(
    project_id: int,
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    credential = await ProjectAppAccessService(db, user=current_user).get_access(
        project_id=project_id,
        app_id=app_id,
    )
    return _response(credential)


@router.post("/project-apps/{project_id}/{app_id}/access", response_model=ProjectAppAccessIssuedResponse)
async def create_project_app_access(
    project_id: int,
    app_id: int,
    body: ProjectAppAccessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    issued = await ProjectAppAccessService(db, user=current_user).create_access(
        project_id=project_id,
        app_id=app_id,
        allowed_origins=body.allowed_origins,
    )
    return _issued_response(issued)


@router.put("/project-apps/{project_id}/{app_id}/access", response_model=ProjectAppAccessResponse)
async def update_project_app_access(
    project_id: int,
    app_id: int,
    body: ProjectAppAccessUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    credential = await ProjectAppAccessService(db, user=current_user).update_access(
        project_id=project_id,
        app_id=app_id,
        allowed_origins=body.allowed_origins,
    )
    return _response(credential)


@router.post("/project-apps/{project_id}/{app_id}/access/enable", response_model=ProjectAppAccessResponse)
async def enable_project_app_access(
    project_id: int,
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    credential = await ProjectAppAccessService(db, user=current_user).enable_access(
        project_id=project_id,
        app_id=app_id,
    )
    return _response(credential)


@router.post(
    "/project-apps/{project_id}/{app_id}/access/reset-secret",
    response_model=ProjectAppAccessIssuedResponse,
)
async def reset_project_app_access_secret(
    project_id: int,
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    issued = await ProjectAppAccessService(db, user=current_user).reset_secret(
        project_id=project_id,
        app_id=app_id,
    )
    return _issued_response(issued)


@router.post("/project-apps/{project_id}/{app_id}/access/revoke", response_model=ProjectAppAccessResponse)
async def revoke_project_app_access(
    project_id: int,
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    credential = await ProjectAppAccessService(db, user=current_user).revoke_access(
        project_id=project_id,
        app_id=app_id,
    )
    return _response(credential)
