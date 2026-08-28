"""Tests for application-managed integration credential encryption."""

import pytest

from app.core.credential_cipher import CredentialCipher


def test_credential_cipher_roundtrip() -> None:
    cipher = CredentialCipher(secret_key="platform-secret")

    encrypted = cipher.encrypt("internal-service-token")

    assert encrypted != "internal-service-token"
    assert cipher.decrypt(encrypted) == "internal-service-token"


def test_credential_cipher_rejects_different_platform_key() -> None:
    encrypted = CredentialCipher(secret_key="platform-secret").encrypt(
        "internal-service-token"
    )

    with pytest.raises(ValueError, match="cannot be decrypted"):
        CredentialCipher(secret_key="different-secret").decrypt(encrypted)
