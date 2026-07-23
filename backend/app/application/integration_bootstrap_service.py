"""Build the browser bootstrap payload from app-scoped client credentials."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.project_app_access_service import ProjectAppAccessService
from app.core.config import settings
from app.core.security import create_widget_token
from app.models.schemas.widget import IntegrationBootstrapCreate
from app.repositories.project_app_access_repository import ProjectAppAccessRepository
from app.repositories.project_repository import ProjectRepository


@dataclass(frozen=True, slots=True)
class IssuedIntegrationBootstrap:
    access_token: str
    expires_in: int
    widget_version: str


class IntegrationBootstrapService:
    def __init__(self, db: AsyncSession) -> None:
        self.access_repository = ProjectAppAccessRepository(db)
        self.project_repository = ProjectRepository(db)
        self.access_service = ProjectAppAccessService(db)

    async def create_bootstrap(
        self,
        *,
        client_id: str,
        client_secret: str,
        payload: IntegrationBootstrapCreate,
    ) -> IssuedIntegrationBootstrap:
        credential = await self.access_repository.get_by_client_id(
            client_id.strip()
        )
        if credential is None or not self.access_service.verify_client_secret(
            credential, client_secret
        ):
            raise HTTPException(status_code=401, detail="Invalid integration client credentials")
        if not credential.enabled:
            raise HTTPException(status_code=403, detail="Project application access is disabled")
        runtime = await self.project_repository.get_runtime_by_app_id(
            project_app_id=credential.project_app_id,
            active_only=True,
        )
        if runtime is None:
            raise HTTPException(status_code=409, detail="Project application runtime is incomplete")
        expires_minutes = max(1, settings.WIDGET_TOKEN_EXPIRE_MINUTES)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        token = create_widget_token(
            client_id=credential.client_id,
            team_id=runtime.project.team_id,
            product_id=runtime.product.id,
            project_id=runtime.project.id,
            project_app_id=runtime.app.id,
            external_user_id=payload.principal.external_user_id.strip(),
            external_user_name=(payload.principal.display_name or "").strip() or None,
            trusted_scope=dict(payload.scope),
            initial_page_type=(payload.initial_page_type or "").strip() or None,
            token_version=credential.token_version,
            expires_at=expires_at,
        )
        return IssuedIntegrationBootstrap(
            access_token=token,
            expires_in=expires_minutes * 60,
            widget_version=runtime.app.widget_version,
        )
