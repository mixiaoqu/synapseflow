"""Authentication dependencies for the AgentChat widget."""

from __future__ import annotations

from secrets import compare_digest

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.widget_chat_service import WidgetSessionContext
from app.core.config import settings
from app.core.security import decode_widget_token

widget_bearer_scheme = HTTPBearer(auto_error=False)


async def require_widget_service_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(widget_bearer_scheme),
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


async def get_widget_session_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(widget_bearer_scheme),
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

    return WidgetSessionContext(
        project_id=int(payload["project_id"]),
        project_app_id=int(payload["project_app_id"]),
        external_user_id=str(payload["external_user_id"]),
        external_user_name=(
            str(payload["external_user_name"])
            if payload.get("external_user_name") is not None
            else None
        ),
        store_id=(str(payload.get("store_id") or "").strip() or None),
        initial_page_type=(str(payload.get("initial_page_type") or "").strip() or None),
    )
