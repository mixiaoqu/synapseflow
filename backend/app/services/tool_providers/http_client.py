"""Shared HTTP transport for external tool providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from app.services.tool_providers.schemas import ToolProviderConfig, ToolProviderError

_MAX_RESPONSE_BYTES = 1024 * 1024
_TIMEOUT = httpx.Timeout(connect=3.0, read=30.0, write=10.0, pool=3.0)
_shared_client: httpx.AsyncClient | None = None


def _get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False)
    return _shared_client


async def close_provider_http_client() -> None:
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
    _shared_client = None


@dataclass(frozen=True, slots=True)
class ProviderHttpResponse:
    status_code: int
    data: dict[str, Any]


class ProviderHttpClient:
    """Perform bounded provider requests through one connection pool."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or _get_shared_client()

    @staticmethod
    def build_url(base_url: str, path: str = "") -> str:
        normalized = str(base_url or "").strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ToolProviderError("工具提供方地址必须是有效的 HTTP 或 HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ToolProviderError("工具提供方地址不能包含凭证、查询参数或片段")
        allowed_hosts = {
            item.strip().lower()
            for item in settings.TOOL_PROVIDER_ALLOWED_HOSTS.split(",")
            if item.strip()
        }
        if allowed_hosts and parsed.hostname.lower() not in allowed_hosts:
            raise ToolProviderError("工具提供方地址不在允许的主机列表中")
        return urljoin(f"{normalized}/", path.lstrip("/")) if path else normalized

    @staticmethod
    def build_auth_headers(provider: ToolProviderConfig) -> dict[str, str]:
        auth_type = provider.auth_type.strip().lower()
        if auth_type == "none":
            return {}
        token = str(provider.auth_token or "").strip()
        if not token:
            raise ToolProviderError("工具提供方未配置 Service Token")
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {token}"}
        if auth_type == "header" and provider.auth_header_name:
            return {provider.auth_header_name: token}
        raise ToolProviderError("不支持的工具提供方鉴权方式")

    async def request_json(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None = None,
    ) -> ProviderHttpResponse:
        try:
            async with self.client.stream(
                method,
                url,
                headers=headers,
                json=payload,
            ) as response:
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > _MAX_RESPONSE_BYTES:
                        raise ToolProviderError("工具提供方响应超过 1 MB 限制")
                    chunks.append(chunk)
        except httpx.TimeoutException as exc:
            raise ToolProviderError("工具提供方请求超时") from exc
        except httpx.HTTPError as exc:
            raise ToolProviderError(f"工具提供方网络请求失败：{exc}") from exc
        raw = b"".join(chunks)
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ToolProviderError("工具提供方返回了无效 JSON") from exc
        if not isinstance(data, dict):
            raise ToolProviderError("工具提供方响应必须是 JSON 对象")
        return ProviderHttpResponse(status_code=response.status_code, data=data)
