"""Object storage helpers for direct browser uploads."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

from tos import TosClientV2
from tos.enum import HttpMethodType
from tos.exceptions import TosClientError, TosServerError

from app.core.config.settings import settings
from app.utils.time import utc_now


@dataclass(frozen=True, slots=True)
class DirectUploadPolicy:
    """Signed browser-upload policy."""

    provider: str
    method: str
    bucket_name: str
    object_key: str
    upload_url: str
    expires_at: datetime
    form_fields: dict[str, str]


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    """Object metadata fetched from the object-storage service."""

    content_length: int
    content_type: str | None
    etag: str | None


class ObjectStorageError(RuntimeError):
    """Base object-storage runtime error."""


class ObjectStorageObjectNotFoundError(ObjectStorageError):
    """Raised when the target object does not exist."""


class ObjectStorageAuthorizationError(ObjectStorageError):
    """Raised when the target object cannot be accessed with current credentials."""


class ObjectStorageService:
    """Generate direct-upload policies for supported object-storage providers."""

    @staticmethod
    def _safe_extension(filename: str) -> str:
        if "." not in filename:
            return ""
        suffix = "." + filename.rsplit(".", 1)[-1].lower()
        return suffix if suffix.replace(".", "").isalnum() else ""

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        raw = (endpoint or "").strip()
        if not raw:
            raise RuntimeError("TOS endpoint is not configured")
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        if not parsed.netloc:
            raise RuntimeError("TOS endpoint is invalid")
        return f"{parsed.scheme or 'https'}://{parsed.netloc}"

    def ensure_enabled(self) -> None:
        if not settings.OSS_ENABLED:
            raise RuntimeError("OSS direct upload is disabled")
        if not settings.OSS_BUCKET.strip():
            raise RuntimeError("TOS bucket is not configured")
        if not settings.OSS_ACCESS_KEY_ID.strip() or not settings.OSS_ACCESS_KEY_SECRET.strip():
            raise RuntimeError("TOS access key is not configured")
        if not settings.OSS_ENDPOINT.strip() or not settings.OSS_REGION.strip():
            raise RuntimeError("TOS endpoint or region is not configured")

    def build_document_object_key(
        self,
        *,
        team_id: int,
        knowledge_base_id: int,
        filename: str,
    ) -> str:
        now = utc_now()
        extension = self._safe_extension(filename)
        return (
            f"team/{team_id}/kb/{knowledge_base_id}/raw/"
            f"{now:%Y/%m/%d}/{uuid4().hex}{extension}"
        )

    @staticmethod
    def _client() -> TosClientV2:
        return TosClientV2(
            ak=settings.OSS_ACCESS_KEY_ID.strip(),
            sk=settings.OSS_ACCESS_KEY_SECRET.strip(),
            endpoint=ObjectStorageService._normalize_endpoint(settings.OSS_ENDPOINT),
            region=settings.OSS_REGION.strip(),
        )

    @staticmethod
    def build_object_change_token(
        *,
        bucket_name: str,
        object_key: str,
        file_size: int,
        etag: str | None,
    ) -> str:
        normalized_etag = (etag or "").strip()
        if normalized_etag:
            return normalized_etag
        payload = f"{bucket_name}:{object_key}:{file_size}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_etag(raw_value: str | None) -> str | None:
        value = (raw_value or "").strip()
        if not value:
            return None
        return value.strip('"')

    def create_browser_upload_policy(
        self,
        *,
        bucket_name: str,
        object_key: str,
        file_size: int,
        content_type: str | None,
    ) -> DirectUploadPolicy:
        self.ensure_enabled()
        provider = settings.OSS_PROVIDER.strip() or "volcengine_tos"
        if provider != "volcengine_tos":
            raise RuntimeError(f"Unsupported TOS provider: {provider}")
        expires_at = utc_now() + timedelta(seconds=max(int(settings.OSS_UPLOAD_EXPIRE_SECONDS), 60))
        normalized_content_type = (content_type or "").strip()
        headers = {"Content-Type": normalized_content_type} if normalized_content_type else None
        signed_url = self._client().pre_signed_url(
            HttpMethodType.Http_Method_Put,
            bucket_name,
            object_key,
            expires=max(int(settings.OSS_UPLOAD_EXPIRE_SECONDS), 60),
            header=headers,
        ).signed_url
        return DirectUploadPolicy(
            provider=provider,
            method="PUT",
            bucket_name=bucket_name,
            object_key=object_key,
            upload_url=signed_url,
            expires_at=expires_at,
            form_fields=headers or {},
        )

    async def head_object(
        self,
        *,
        bucket_name: str,
        object_key: str,
    ) -> ObjectMetadata:
        self.ensure_enabled()
        provider = settings.OSS_PROVIDER.strip() or "volcengine_tos"
        if provider != "volcengine_tos":
            raise ObjectStorageError(f"Unsupported TOS provider: {provider}")
        try:
            metadata = await asyncio.to_thread(self._client().head_object, bucket_name, object_key)
        except TosServerError as exc:
            self._raise_tos_error(exc, "reading object metadata")
        except TosClientError as exc:
            raise ObjectStorageError(f"TOS client error while reading object metadata: {exc}") from exc
        return ObjectMetadata(
            content_length=int(getattr(metadata, "content_length", 0) or 0),
            content_type=(getattr(metadata, "content_type", None) or "").strip() or None,
            etag=self._normalize_etag(getattr(metadata, "etag", None)),
        )

    async def get_object_bytes(
        self,
        *,
        bucket_name: str,
        object_key: str,
    ) -> bytes:
        self.ensure_enabled()
        provider = settings.OSS_PROVIDER.strip() or "volcengine_tos"
        if provider != "volcengine_tos":
            raise ObjectStorageError(f"Unsupported TOS provider: {provider}")
        try:
            result = await asyncio.to_thread(self._client().get_object, bucket_name, object_key)
            return await asyncio.to_thread(result.read)
        except TosServerError as exc:
            self._raise_tos_error(exc, "downloading object bytes")
        except TosClientError as exc:
            raise ObjectStorageError(f"TOS client error while downloading object bytes: {exc}") from exc

    @staticmethod
    def _raise_tos_error(exc: TosServerError, operation: str) -> None:
        status_code = getattr(exc, "status_code", None)
        if status_code == 404:
            raise ObjectStorageObjectNotFoundError("Uploaded object does not exist in TOS") from exc
        if status_code in {401, 403}:
            raise ObjectStorageAuthorizationError("Failed to access uploaded object in TOS") from exc
        raise ObjectStorageError(
            f"Unexpected TOS response status={status_code} while {operation}"
        ) from exc


object_storage_service = ObjectStorageService()
