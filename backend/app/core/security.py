"""Authentication helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(*, subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    expire_at = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": subject,
        "type": "access",
        "exp": expire_at,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_embed_token(
    *,
    project_id: int,
    project_app_id: int,
    external_user_id: str,
    external_user_name: str | None = None,
    source: str | None = None,
    initial_page_type: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a short-lived token for embedded assistant iframes."""

    expire_at = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.EMBED_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": external_user_id,
        "type": "embed",
        "project_id": project_id,
        "project_app_id": project_app_id,
        "external_user_id": external_user_id,
        "external_user_name": external_user_name,
        "source": source,
        "initial_page_type": initial_page_type,
        "exp": expire_at,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid authentication token") from exc

    if payload.get("type") != "access":
        raise ValueError("Invalid authentication token")
    if not payload.get("sub"):
        raise ValueError("Invalid authentication token")
    return payload


def decode_embed_token(token: str) -> dict:
    """Decode and validate a short-lived embedded assistant token."""

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except ExpiredSignatureError as exc:
        raise ValueError("Embedded assistant token expired") from exc
    except JWTError as exc:
        raise ValueError("Invalid embedded assistant token") from exc

    if payload.get("type") != "embed":
        raise ValueError("Invalid embedded assistant token")
    if not payload.get("external_user_id"):
        raise ValueError("Invalid embedded assistant token")
    try:
        int(payload["project_id"])
        int(payload["project_app_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid embedded assistant token") from exc
    return payload
