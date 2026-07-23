"""Application service for project application access credentials."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.permission_service import PermissionService
from app.core.authz import PERMISSION_MANAGE_PROJECT
from app.core.config import settings
from app.db.models import ProjectApp, ProjectAppAccessCredential, User
from app.repositories.project_app_access_repository import ProjectAppAccessRepository


@dataclass(slots=True)
class IssuedProjectAppCredential:
    credential: ProjectAppAccessCredential
    client_secret: str

    @property
    def client_id(self) -> str:
        return self.credential.client_id


class ProjectAppAccessService:
    """Create, verify, reset and revoke app-scoped client credentials."""

    def __init__(self, db: AsyncSession, *, user: User | None = None) -> None:
        self.db = db
        self.user = user
        self.repository = ProjectAppAccessRepository(db)
        self.permission_service = PermissionService(db)
        self.secret_pepper = settings.INTEGRATION_CREDENTIAL_PEPPER.strip()
        if not self.secret_pepper:
            raise RuntimeError("INTEGRATION_CREDENTIAL_PEPPER is not configured")

    async def _get_managed_app(self, *, project_id: int, app_id: int) -> ProjectApp:
        app = await self.repository.get_project_app(project_id=project_id, app_id=app_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Project application not found")
        team_id = await self.repository.get_project_app_team_id(
            project_id=project_id, app_id=app_id
        )
        allowed = (
            self.user is not None
            and team_id is not None
            and await self.permission_service.has_team_permission(
                self.user, team_id, PERMISSION_MANAGE_PROJECT
            )
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Team access denied")
        return app

    def _digest(self, secret: str) -> str:
        return hmac.new(
            self.secret_pepper.encode("utf-8"),
            secret.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _generate_client_id() -> str:
        return f"sfc_{secrets.token_urlsafe(18)}"

    @staticmethod
    def _generate_client_secret() -> str:
        return f"sfs_{secrets.token_urlsafe(32)}"

    @staticmethod
    def _normalize_origins(origins: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw_origin in origins:
            value = str(raw_origin).strip().rstrip("/")
            parsed = urlsplit(value)
            if (
                parsed.scheme.lower() not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Allowed origins must be HTTP origins without paths",
                )
            normalized_origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
            if normalized_origin not in normalized:
                normalized.append(normalized_origin)
        if not normalized:
            raise HTTPException(
                status_code=400,
                detail="At least one valid HTTP origin is required",
            )
        return normalized

    async def create_access(
        self,
        *,
        project_id: int,
        app_id: int,
        allowed_origins: list[str],
    ) -> IssuedProjectAppCredential:
        app = await self._get_managed_app(project_id=project_id, app_id=app_id)
        if await self.repository.get_by_app(app.id) is not None:
            raise HTTPException(status_code=409, detail="Project application access already exists")
        client_secret = self._generate_client_secret()
        credential = ProjectAppAccessCredential(
            project_app_id=app.id,
            client_id=self._generate_client_id(),
            client_secret_digest=self._digest(client_secret),
            client_secret_last_four=client_secret[-4:],
            allowed_origins=self._normalize_origins(allowed_origins),
            token_version=1,
            enabled=True,
        )
        saved = await self.repository.save(credential)
        return IssuedProjectAppCredential(credential=saved, client_secret=client_secret)

    async def reset_secret(
        self,
        *,
        project_id: int,
        app_id: int,
    ) -> IssuedProjectAppCredential:
        app = await self._get_managed_app(project_id=project_id, app_id=app_id)
        credential = await self.repository.get_by_app(app.id)
        if credential is None:
            raise HTTPException(status_code=404, detail="Project application access not found")
        client_secret = self._generate_client_secret()
        credential.client_secret_digest = self._digest(client_secret)
        credential.client_secret_last_four = client_secret[-4:]
        credential.token_version = int(credential.token_version or 0) + 1
        credential.enabled = True
        saved = await self.repository.save(credential)
        return IssuedProjectAppCredential(credential=saved, client_secret=client_secret)

    async def get_access(self, *, project_id: int, app_id: int) -> ProjectAppAccessCredential:
        app = await self._get_managed_app(project_id=project_id, app_id=app_id)
        credential = await self.repository.get_by_app(app.id)
        if credential is None:
            raise HTTPException(status_code=404, detail="Project application access not found")
        return credential

    async def update_access(
        self,
        *,
        project_id: int,
        app_id: int,
        allowed_origins: list[str],
    ) -> ProjectAppAccessCredential:
        credential = await self.get_access(project_id=project_id, app_id=app_id)
        credential.allowed_origins = self._normalize_origins(allowed_origins)
        return await self.repository.save(credential)

    async def enable_access(
        self,
        *,
        project_id: int,
        app_id: int,
    ) -> ProjectAppAccessCredential:
        credential = await self.get_access(project_id=project_id, app_id=app_id)
        credential.enabled = True
        return await self.repository.save(credential)

    async def revoke_access(
        self,
        *,
        project_id: int,
        app_id: int,
    ) -> ProjectAppAccessCredential:
        credential = await self.get_access(project_id=project_id, app_id=app_id)
        credential.enabled = False
        credential.token_version = int(credential.token_version or 0) + 1
        return await self.repository.save(credential)

    def verify_client_secret(
        self,
        credential: ProjectAppAccessCredential,
        client_secret: str,
    ) -> bool:
        return hmac.compare_digest(
            str(credential.client_secret_digest or ""),
            self._digest(str(client_secret or "")),
        )
