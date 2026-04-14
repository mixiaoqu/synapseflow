from app.core.authz import (
    ADMIN_ROLES,
    ROLE_END_USER,
    ROLE_KB_ADMIN,
    ROLE_KB_EDITOR,
    has_any_role,
    normalize_role,
)


def test_normalize_role_defaults_to_end_user():
    assert normalize_role(None) == ROLE_END_USER
    assert normalize_role("") == ROLE_END_USER


def test_has_any_role_matches_normalized_roles():
    assert has_any_role("KB_ADMIN", ADMIN_ROLES) is True
    assert has_any_role(ROLE_KB_EDITOR, ADMIN_ROLES) is True
    assert has_any_role(ROLE_END_USER, ADMIN_ROLES) is False


def test_has_any_role_matches_kb_admin_exactly():
    assert has_any_role(ROLE_KB_ADMIN, [ROLE_KB_ADMIN]) is True
    assert has_any_role(ROLE_KB_EDITOR, [ROLE_KB_ADMIN]) is False
