"""Authentication dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import (
    ADMIN_ROLES,
    CONTENT_ROLES,
    REVIEW_ROLES,
    ROLE_KB_ADMIN,
    has_any_role,
)
from app.db.models import User
from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the current authenticated user from a bearer token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
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
    return user


def require_roles(*roles: str):
    async def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if not has_any_role(getattr(current_user, "role", None), roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _dependency


def require_any_admin_role(
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
) -> User:
    return current_user


def require_content_roles(
    current_user: User = Depends(require_roles(*CONTENT_ROLES)),
) -> User:
    return current_user


def require_review_roles(
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
) -> User:
    return current_user


def require_kb_admin_role(
    current_user: User = Depends(require_roles(ROLE_KB_ADMIN)),
) -> User:
    return current_user
