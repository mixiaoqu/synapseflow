"""Authorization roles and helpers."""

from __future__ import annotations

from collections.abc import Iterable

ROLE_END_USER = "end_user"
ROLE_KB_EDITOR = "kb_editor"
ROLE_KB_REVIEWER = "kb_reviewer"
ROLE_KB_ADMIN = "kb_admin"

ADMIN_ROLES: tuple[str, ...] = (
    ROLE_KB_EDITOR,
    ROLE_KB_REVIEWER,
    ROLE_KB_ADMIN,
)
CONTENT_ROLES: tuple[str, ...] = (
    ROLE_KB_EDITOR,
    ROLE_KB_ADMIN,
)
REVIEW_ROLES: tuple[str, ...] = (
    ROLE_KB_REVIEWER,
    ROLE_KB_ADMIN,
)


def normalize_role(role: str | None) -> str:
    value = (role or "").strip().lower()
    return value or ROLE_END_USER


def has_any_role(role: str | None, allowed_roles: Iterable[str]) -> bool:
    normalized = normalize_role(role)
    return normalized in {normalize_role(item) for item in allowed_roles}
