"""Authentication dependencies for the AgentChat widget."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.widget_chat_service import WidgetSessionContext
from app.core.security import decode_widget_token
from app.db.session import get_db
from app.repositories.project_app_access_repository import ProjectAppAccessRepository

widget_bearer_scheme = HTTPBearer(auto_error=False)


def validate_widget_access(*, credential, token_payload: dict, origin: str | None) -> None:
    if credential is None or not credential.enabled:
        raise HTTPException(status_code=401, detail="Widget access is disabled")
    if int(token_payload.get("token_version") or 0) != int(credential.token_version or 0):
        raise HTTPException(status_code=401, detail="Widget token has been revoked")
    normalized_origin = str(origin or "").strip().rstrip("/")
    allowed_origins = {
        str(item).strip().rstrip("/") for item in list(credential.allowed_origins or [])
    }
    if normalized_origin and normalized_origin not in allowed_origins:
        raise HTTPException(status_code=403, detail="Widget origin is not allowed")


async def get_widget_session_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(widget_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> WidgetSessionContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Widget token is required",
        )
    try:
        payload = decode_widget_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    credential = await ProjectAppAccessRepository(db).get_by_app(
        int(payload["project_app_id"])
    )
    validate_widget_access(
        credential=credential,
        token_payload=payload,
        origin=request.headers.get("origin"),
    )
    trusted_scope = dict(payload.get("trusted_scope") or {})

    return WidgetSessionContext(
        team_id=int(payload["team_id"]),
        product_id=int(payload["product_id"]),
        project_id=int(payload["project_id"]),
        project_app_id=int(payload["project_app_id"]),
        external_user_id=str(payload["external_user_id"]),
        external_user_name=(
            str(payload["external_user_name"])
            if payload.get("external_user_name") is not None
            else None
        ),
        trusted_scope=trusted_scope,
        store_id=(str(trusted_scope.get("store_id") or "").strip() or None),
        initial_page_type=(str(payload.get("initial_page_type") or "").strip() or None),
    )
