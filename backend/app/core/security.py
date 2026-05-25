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
        "initial_page_type": initial_page_type,
        "exp": expire_at,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_mcp_token(
    *,
    product_id: int,
    project_id: int,
    project_app_id: int,
    product_code: str,
    project_code: str,
    app_code: str,
    client_user_id: str,
    client_user_name: str | None = None,
    client_editor: str | None = None,
    client_host: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a short-lived token for MCP knowledge access."""

    expire_at = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.MCP_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": client_user_id,
        "type": "mcp_access",
        "product_id": product_id,
        "project_id": project_id,
        "project_app_id": project_app_id,
        "product_code": product_code,
        "project_code": project_code,
        "app_code": app_code,
        "client_user_id": client_user_id,
        "client_user_name": client_user_name,
        "client_editor": client_editor,
        "client_host": client_host,
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


def decode_mcp_token(token: str) -> dict:
    """Decode and validate a short-lived MCP access token."""

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except ExpiredSignatureError as exc:
        raise ValueError("MCP access token expired") from exc
    except JWTError as exc:
        raise ValueError("Invalid MCP access token") from exc

    if payload.get("type") != "mcp_access":
        raise ValueError("Invalid MCP access token")
    if not payload.get("client_user_id"):
        raise ValueError("Invalid MCP access token")
    for key in ("product_id", "project_id", "project_app_id"):
        try:
            int(payload[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid MCP access token") from exc
    for key in ("product_code", "project_code", "app_code"):
        value = str(payload.get(key) or "").strip()
        if not value:
            raise ValueError("Invalid MCP access token")
    return payload
