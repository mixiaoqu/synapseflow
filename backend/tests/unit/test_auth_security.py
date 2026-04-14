"""Tests for authentication helpers and settings coercion."""

from app.core.config.settings import Settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


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


def test_settings_debug_aliases():
    assert Settings(_env_file=None, DEBUG="release").DEBUG is False
    assert Settings(_env_file=None, DEBUG="production").DEBUG is False
    assert Settings(_env_file=None, DEBUG="dev").DEBUG is True
    assert Settings(_env_file=None, DEBUG="development").DEBUG is True
