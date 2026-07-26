from app.core.authz import (
    PERMISSION_VIEW_TEAM_RESOURCE,
    SYSTEM_ADMIN_ROLES,
    SYSTEM_ROLE_USER,
    TEAM_ROLE_VIEWER,
    has_any_role,
    has_team_role_permission,
    normalize_role,
    normalize_team_role,
)


def test_normalize_role_defaults_to_user():
    assert normalize_role(None) == SYSTEM_ROLE_USER
    assert normalize_role("") == SYSTEM_ROLE_USER
    assert normalize_role("unknown") == SYSTEM_ROLE_USER


def test_has_any_role_matches_platform_roles():
    assert has_any_role("SYSTEM_ADMIN", SYSTEM_ADMIN_ROLES) is True
    assert has_any_role(SYSTEM_ROLE_USER, SYSTEM_ADMIN_ROLES) is False


def test_normalize_team_role_defaults_unknown_to_viewer():
    assert normalize_team_role("unknown") == TEAM_ROLE_VIEWER
    assert has_team_role_permission("viewer", PERMISSION_VIEW_TEAM_RESOURCE) is True
