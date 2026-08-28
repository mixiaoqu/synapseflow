"""Tests for authentication helpers and settings coercion."""

from app.core.config.settings import Settings
from app.core.security import (
    create_access_token,
    create_mcp_token,
    decode_access_token,
    decode_mcp_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    password = "Passw0rd!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token(subject="123")
    payload = decode_access_token(token)

    assert payload["sub"] == "123"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_mcp_token_roundtrip():
    token = create_mcp_token(
        product_id=1,
        project_id=2,
        project_app_id=3,
        product_code="test",
        project_code="test",
        app_code="test",
        client_user_id="zhangsan",
        client_user_name="张三",
        client_editor="trae",
        client_host="DESKTOP-001",
    )
    payload = decode_mcp_token(token)

    assert payload["type"] == "mcp_access"
    assert payload["project_app_id"] == 3
    assert payload["client_user_id"] == "zhangsan"


def test_settings_debug_aliases():
    assert Settings(_env_file=None, DEBUG="release").DEBUG is False
    assert Settings(_env_file=None, DEBUG="production").DEBUG is False
    assert Settings(_env_file=None, DEBUG="dev").DEBUG is True
    assert Settings(_env_file=None, DEBUG="development").DEBUG is True
