"""Authorization roles, permissions and helpers."""

from __future__ import annotations

from collections.abc import Iterable

SYSTEM_ROLE_ADMIN = "system_admin"
SYSTEM_ROLE_OPERATOR = "system_operator"
SYSTEM_ROLE_USER = "user"

SYSTEM_ROLES: tuple[str, ...] = (
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_OPERATOR,
    SYSTEM_ROLE_USER,
)
SYSTEM_ADMIN_ROLES: tuple[str, ...] = (SYSTEM_ROLE_ADMIN,)

TEAM_ROLE_OWNER = "owner"
TEAM_ROLE_ADMIN = "admin"
TEAM_ROLE_EDITOR = "editor"
TEAM_ROLE_REVIEWER = "reviewer"
TEAM_ROLE_VIEWER = "viewer"

TEAM_ROLES: tuple[str, ...] = (
    TEAM_ROLE_OWNER,
    TEAM_ROLE_ADMIN,
    TEAM_ROLE_EDITOR,
    TEAM_ROLE_REVIEWER,
    TEAM_ROLE_VIEWER,
)

PERMISSION_VIEW_TEAM_RESOURCE = "view_team_resource"
PERMISSION_MANAGE_TEAM_MEMBER = "manage_team_member"
PERMISSION_DELETE_TEAM = "delete_team"
PERMISSION_MANAGE_PROJECT = "manage_project"
PERMISSION_MANAGE_KB_DRAFT = "manage_kb_draft"
PERMISSION_REVIEW_DOCUMENT = "review_document"
PERMISSION_MANAGE_ASSISTANT = "manage_assistant"
PERMISSION_VIEW_QA_LOG = "view_qa_log"
PERMISSION_REVIEW_QA_LOG = "review_qa_log"
PERMISSION_MANAGE_CONTENT_RISK = "manage_content_risk"

TEAM_ROLE_PERMISSIONS: dict[str, set[str]] = {
    TEAM_ROLE_OWNER: {
        PERMISSION_VIEW_TEAM_RESOURCE,
        PERMISSION_MANAGE_TEAM_MEMBER,
        PERMISSION_DELETE_TEAM,
        PERMISSION_MANAGE_PROJECT,
        PERMISSION_MANAGE_KB_DRAFT,
        PERMISSION_REVIEW_DOCUMENT,
        PERMISSION_MANAGE_ASSISTANT,
        PERMISSION_VIEW_QA_LOG,
        PERMISSION_REVIEW_QA_LOG,
        PERMISSION_MANAGE_CONTENT_RISK,
    },
    TEAM_ROLE_ADMIN: {
        PERMISSION_VIEW_TEAM_RESOURCE,
        PERMISSION_MANAGE_TEAM_MEMBER,
        PERMISSION_MANAGE_PROJECT,
        PERMISSION_MANAGE_KB_DRAFT,
        PERMISSION_REVIEW_DOCUMENT,
        PERMISSION_MANAGE_ASSISTANT,
        PERMISSION_VIEW_QA_LOG,
        PERMISSION_REVIEW_QA_LOG,
        PERMISSION_MANAGE_CONTENT_RISK,
    },
    TEAM_ROLE_EDITOR: {
        PERMISSION_VIEW_TEAM_RESOURCE,
        PERMISSION_MANAGE_PROJECT,
        PERMISSION_MANAGE_KB_DRAFT,
        PERMISSION_MANAGE_ASSISTANT,
        PERMISSION_VIEW_QA_LOG,
    },
    TEAM_ROLE_REVIEWER: {
        PERMISSION_VIEW_TEAM_RESOURCE,
        PERMISSION_REVIEW_DOCUMENT,
        PERMISSION_VIEW_QA_LOG,
        PERMISSION_REVIEW_QA_LOG,
        PERMISSION_MANAGE_CONTENT_RISK,
    },
    TEAM_ROLE_VIEWER: {
        PERMISSION_VIEW_TEAM_RESOURCE,
        PERMISSION_VIEW_QA_LOG,
    },
}

def normalize_role(role: str | None) -> str:
    value = (role or "").strip().lower()
    return value if value in SYSTEM_ROLES else SYSTEM_ROLE_USER


def has_any_role(role: str | None, allowed_roles: Iterable[str]) -> bool:
    normalized = normalize_role(role)
    return normalized in {normalize_role(item) for item in allowed_roles}


def normalize_system_role(role: str | None) -> str:
    normalized = normalize_role(role)
    return normalized if normalized in SYSTEM_ROLES else SYSTEM_ROLE_USER


def normalize_team_role(role: str | None) -> str:
    value = (role or "").strip().lower()
    return value if value in TEAM_ROLES else TEAM_ROLE_VIEWER


def has_team_role_permission(role: str | None, permission: str) -> bool:
    return permission in TEAM_ROLE_PERMISSIONS.get(normalize_team_role(role), set())
