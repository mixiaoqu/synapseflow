"""Dependencies for MCP access tokens and backward-compatible user auth."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import bearer_scheme
from app.core.security import decode_access_token, decode_mcp_token
from app.db.models import User
from app.db.session import get_db
from app.repositories.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class McpTokenContext:
    product_id: int
    project_id: int
    project_app_id: int
    product_code: str
    project_code: str
    app_code: str
    client_user_id: str
    client_user_name: str | None
    client_editor: str | None
    client_host: str | None


@dataclass(frozen=True, slots=True)
class McpAuthContext:
    user: User | None
    mcp_token: McpTokenContext | None


def _build_mcp_token_context(payload: dict) -> McpTokenContext:
    return McpTokenContext(
        product_id=int(payload["product_id"]),
        project_id=int(payload["project_id"]),
        project_app_id=int(payload["project_app_id"]),
        product_code=str(payload["product_code"]).strip(),
        project_code=str(payload["project_code"]).strip(),
        app_code=str(payload["app_code"]).strip(),
        client_user_id=str(payload["client_user_id"]).strip(),
        client_user_name=(
            str(payload["client_user_name"]).strip()
            if payload.get("client_user_name") is not None
            else None
        )
        or None,
        client_editor=(
            str(payload["client_editor"]).strip()
            if payload.get("client_editor") is not None
            else None
        )
        or None,
        client_host=(
            str(payload["client_host"]).strip()
            if payload.get("client_host") is not None
            else None
        )
        or None,
    )


async def get_mcp_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> McpAuthContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = credentials.credentials
    try:
        payload = decode_mcp_token(token)
    except ValueError:
        payload = None

    if payload is not None:
        return McpAuthContext(user=None, mcp_token=_build_mcp_token_context(payload))

    try:
        access_payload = decode_access_token(token)
        user_id = int(access_payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from None

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication user no longer exists",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return McpAuthContext(user=user, mcp_token=None)
