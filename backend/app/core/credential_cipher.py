"""Encryption helper for application-managed integration credentials."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class CredentialCipher:
    """Encrypt and decrypt integration secrets with a purpose-derived platform key."""

    _PURPOSE = b"synapseflow:mcp-server-credential:v1"

    def __init__(self, secret_key: str | None = None) -> None:
        root_key = str(secret_key or settings.SECRET_KEY).encode("utf-8")
        derived_key = hashlib.sha256(self._PURPOSE + b":" + root_key).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(derived_key))

    def encrypt(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("Credential cannot be empty")
        return self._fernet.encrypt(normalized.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(str(value or "").encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError, ValueError) as exc:
            raise ValueError("Stored MCP credential cannot be decrypted") from exc
