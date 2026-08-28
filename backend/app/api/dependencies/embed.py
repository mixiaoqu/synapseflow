"""Dependencies for service-to-service and embedded assistant auth."""

from __future__ import annotations

from dataclasses import dataclass
from secrets import compare_digest

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.security import decode_embed_token

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class EmbedTokenContext:
    project_id: int
    project_app_id: int
    external_user_id: str
    external_user_name: str | None
    store_id: str | None
    initial_page_type: str | None


async def require_enterprise_service_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    configured_token = settings.ENTERPRISE_SERVICE_TOKEN.strip()
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Enterprise service token is not configured",
        )
    if credentials is None or not compare_digest(credentials.credentials, configured_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid enterprise service token",
        )


async def get_embed_token_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> EmbedTokenContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Embedded assistant token is required",
        )
    try:
        payload = decode_embed_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return EmbedTokenContext(
        project_id=int(payload["project_id"]),
        project_app_id=int(payload["project_app_id"]),
        external_user_id=str(payload["external_user_id"]),
        external_user_name=(
            str(payload["external_user_name"])
            if payload.get("external_user_name") is not None
            else None
        ),
        store_id=(
            str(payload["store_id"]).strip()
            if payload.get("store_id") is not None
            else None
        )
        or None,
        initial_page_type=(
            str(payload["initial_page_type"]).strip()
            if payload.get("initial_page_type") is not None
            else None
        )
        or None,
    )
