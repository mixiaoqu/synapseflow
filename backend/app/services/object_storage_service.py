"""Object storage helpers for direct browser uploads."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import format_datetime
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx

from app.core.config.settings import settings
from app.utils.time import serialize_utc_datetime, utc_now


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
    def _normalize_endpoint(endpoint: str) -> tuple[str, str]:
        raw = (endpoint or "").strip()
        if not raw:
            raise RuntimeError("OSS endpoint is not configured")
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        if not parsed.netloc:
            raise RuntimeError("OSS endpoint is invalid")
        return parsed.scheme or "https", parsed.netloc

    def ensure_enabled(self) -> None:
        if not settings.OSS_ENABLED:
            raise RuntimeError("OSS direct upload is disabled")
        if not settings.OSS_BUCKET.strip():
            raise RuntimeError("OSS bucket is not configured")
        if not settings.OSS_ACCESS_KEY_ID.strip() or not settings.OSS_ACCESS_KEY_SECRET.strip():
            raise RuntimeError("OSS access key is not configured")

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
    def _build_bucket_url(bucket_name: str, endpoint: str) -> str:
        scheme, host = ObjectStorageService._normalize_endpoint(endpoint)
        if host.startswith(f"{bucket_name}."):
            return f"{scheme}://{host}"
        return f"{scheme}://{bucket_name}.{host}"

    def _build_bucket_upload_url(self, bucket_name: str) -> str:
        public_endpoint = settings.OSS_PUBLIC_ENDPOINT.strip() or settings.OSS_ENDPOINT.strip()
        return self._build_bucket_url(bucket_name, public_endpoint)

    def _build_bucket_service_url(self, bucket_name: str) -> str:
        return self._build_bucket_url(bucket_name, settings.OSS_ENDPOINT.strip())

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

    def _build_oss_headers(
        self,
        *,
        method: str,
        bucket_name: str,
        object_key: str,
    ) -> dict[str, str]:
        date_value = format_datetime(utc_now(), usegmt=True)
        canonical_resource = f"/{bucket_name}/{object_key}"
        string_to_sign = f"{method}\n\n\n{date_value}\n{canonical_resource}"
        signature = base64.b64encode(
            hmac.new(
                settings.OSS_ACCESS_KEY_SECRET.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")
        return {
            "Date": date_value,
            "Authorization": f"OSS {settings.OSS_ACCESS_KEY_ID.strip()}:{signature}",
        }

    def create_browser_upload_policy(
        self,
        *,
        bucket_name: str,
        object_key: str,
        file_size: int,
        content_type: str | None,
    ) -> DirectUploadPolicy:
        self.ensure_enabled()
        provider = settings.OSS_PROVIDER.strip() or "aliyun_oss"
        if provider != "aliyun_oss":
            raise RuntimeError(f"Unsupported OSS provider: {provider}")

        expires_at = utc_now() + timedelta(seconds=max(int(settings.OSS_UPLOAD_EXPIRE_SECONDS), 60))
        conditions: list[object] = [
            {"bucket": bucket_name},
            {"key": object_key},
            {"success_action_status": "204"},
            ["content-length-range", 1, int(file_size)],
        ]
        form_fields = {
            "key": object_key,
            "success_action_status": "204",
        }
        normalized_content_type = (content_type or "").strip()
        if normalized_content_type:
            conditions.append(["eq", "$Content-Type", normalized_content_type])
            form_fields["Content-Type"] = normalized_content_type

        policy_payload = {
            "expiration": serialize_utc_datetime(expires_at),
            "conditions": conditions,
        }
        policy_json = json.dumps(policy_payload, separators=(",", ":"), ensure_ascii=False)
        encoded_policy = base64.b64encode(policy_json.encode("utf-8")).decode("utf-8")
        signature = base64.b64encode(
            hmac.new(
                settings.OSS_ACCESS_KEY_SECRET.encode("utf-8"),
                encoded_policy.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        form_fields.update(
            {
                "policy": encoded_policy,
                "OSSAccessKeyId": settings.OSS_ACCESS_KEY_ID.strip(),
                "Signature": signature,
            }
        )
        return DirectUploadPolicy(
            provider=provider,
            method="POST",
            bucket_name=bucket_name,
            object_key=object_key,
            upload_url=self._build_bucket_upload_url(bucket_name),
            expires_at=expires_at,
            form_fields=form_fields,
        )

    async def head_object(
        self,
        *,
        bucket_name: str,
        object_key: str,
    ) -> ObjectMetadata:
        self.ensure_enabled()
        provider = settings.OSS_PROVIDER.strip() or "aliyun_oss"
        if provider != "aliyun_oss":
            raise ObjectStorageError(f"Unsupported OSS provider: {provider}")

        object_url = f"{self._build_bucket_service_url(bucket_name)}/{quote(object_key, safe='/')}"
        headers = self._build_oss_headers(
            method="HEAD",
            bucket_name=bucket_name,
            object_key=object_key,
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.head(object_url, headers=headers)

        if response.status_code == 404:
            raise ObjectStorageObjectNotFoundError("Uploaded object does not exist in OSS")
        if response.status_code in {401, 403}:
            raise ObjectStorageAuthorizationError("Failed to access uploaded object in OSS")
        if response.status_code >= 400:
            raise ObjectStorageError(
                f"Unexpected OSS response status={response.status_code} while reading object metadata"
            )

        raw_length = response.headers.get("Content-Length", "0").strip()
        try:
            content_length = int(raw_length)
        except ValueError:
            content_length = 0
        return ObjectMetadata(
            content_length=content_length,
            content_type=(response.headers.get("Content-Type") or "").strip() or None,
            etag=self._normalize_etag(response.headers.get("ETag")),
        )

    async def get_object_bytes(
        self,
        *,
        bucket_name: str,
        object_key: str,
    ) -> bytes:
        self.ensure_enabled()
        provider = settings.OSS_PROVIDER.strip() or "aliyun_oss"
        if provider != "aliyun_oss":
            raise ObjectStorageError(f"Unsupported OSS provider: {provider}")

        object_url = f"{self._build_bucket_service_url(bucket_name)}/{quote(object_key, safe='/')}"
        headers = self._build_oss_headers(
            method="GET",
            bucket_name=bucket_name,
            object_key=object_key,
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(object_url, headers=headers)

        if response.status_code == 404:
            raise ObjectStorageObjectNotFoundError("Uploaded object does not exist in OSS")
        if response.status_code in {401, 403}:
            raise ObjectStorageAuthorizationError("Failed to access uploaded object in OSS")
        if response.status_code >= 400:
            raise ObjectStorageError(
                f"Unexpected OSS response status={response.status_code} while downloading object bytes"
            )
        return response.content


object_storage_service = ObjectStorageService()
