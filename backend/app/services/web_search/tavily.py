"""Tavily REST 适配：固定上游、限时限量、仅发送公开查询和选中的 URL。"""

import asyncio
import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

import httpx
from loguru import logger

from app.services.web_search.schemas import (
    MAX_EXTRACT_PAGES,
    MAX_PAGE_CHARS,
    MAX_QUERY_CHARS,
    MAX_SEARCH_RESULTS,
    WebPage,
    WebSearchError,
    public_web_url,
)

_BASE_URL = "https://api.tavily.com"
_MAX_RESPONSE_BYTES = 1024 * 1024


class TavilyGateway:
    def __init__(self, *, api_key: str, transport: httpx.AsyncBaseTransport | None = None):
        self._api_key = api_key
        self._transport = transport

    async def _request(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        status = "success"
        try:
            async with (
                asyncio.timeout(30),
                httpx.AsyncClient(
                    timeout=httpx.Timeout(25, connect=3),
                    follow_redirects=False,
                    transport=self._transport,
                ) as client,
            ):
                async with client.stream(
                    "POST",
                    f"{_BASE_URL}/{operation}",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                ) as response:
                    if response.status_code in {401, 403}:
                        raise WebSearchError("WEB_AUTH_ERROR", "联网搜索密钥无效或无访问权限。")
                    if response.status_code in {429, 432, 433}:
                        raise WebSearchError("WEB_RATE_LIMIT", "联网搜索达到频率或额度限制。")
                    if response.status_code >= 500:
                        raise WebSearchError(
                            "WEB_UPSTREAM_ERROR", "联网搜索服务暂时异常。", retryable=True
                        )
                    if response.status_code != 200:
                        raise WebSearchError("WEB_HTTP_ERROR", "联网搜索请求被上游拒绝。")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > _MAX_RESPONSE_BYTES:
                            raise WebSearchError(
                                "WEB_RESPONSE_TOO_LARGE", "联网搜索响应超过大小限制。"
                            )
            data = json.loads(body)
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise WebSearchError("WEB_INVALID_RESPONSE", "联网搜索返回了无效的数据结构。")
            return data
        except (TimeoutError, httpx.TimeoutException) as exc:
            status = "WEB_TIMEOUT"
            raise WebSearchError(status, "联网搜索请求超时。", retryable=True) from exc
        except httpx.HTTPError as exc:
            status = "WEB_NETWORK_ERROR"
            raise WebSearchError(status, "联网搜索网络连接失败。", retryable=True) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            status = "WEB_INVALID_RESPONSE"
            raise WebSearchError(status, "联网搜索返回了无效的 JSON。") from exc
        except WebSearchError as exc:
            status = exc.code
            raise
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        finally:
            # 不记录密钥、搜索词、URL 或网页正文。
            logger.info(
                "[联网搜索] operation={} status={} duration_ms={}",
                operation,
                status,
                int((perf_counter() - started) * 1000),
            )

    async def search(self, query: str) -> list[WebPage]:
        query = query.strip()
        if not query or len(query) > MAX_QUERY_CHARS:
            raise WebSearchError(
                "WEB_INVALID_QUERY", f"公开搜索词须为 1–{MAX_QUERY_CHARS} 个字符。"
            )
        data = await self._request(
            "search",
            {
                "query": query,
                "search_depth": "basic",
                "topic": "general",
                "max_results": MAX_SEARCH_RESULTS,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "auto_parameters": False,
            },
        )
        fetched_at = datetime.now(timezone.utc).isoformat()
        pages: list[WebPage] = []
        seen: set[str] = set()
        for item in data["results"][:MAX_SEARCH_RESULTS]:
            if not isinstance(item, dict):
                raise WebSearchError("WEB_INVALID_RESPONSE", "搜索结果条目无效。")
            url = public_web_url(item.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)
            pages.append(
                {
                    "url": url,
                    "title": str(item.get("title") or url)[:300],
                    "snippet": str(item.get("content") or "")[:1500],
                    "published_at": (
                        str(item["published_date"])[:100] if item.get("published_date") else None
                    ),
                    "fetched_at": fetched_at,
                }
            )
        return pages

    async def extract(self, urls: list[str]) -> dict[str, str]:
        if not 1 <= len(urls) <= MAX_EXTRACT_PAGES or any(
            public_web_url(url) != url for url in urls
        ):
            raise WebSearchError("WEB_INVALID_URL", "正文提取仅接受有限数量的公开网页地址。")
        data = await self._request(
            "extract",
            {
                "urls": urls,
                "extract_depth": "basic",
                "format": "markdown",
                "timeout": 15,
            },
        )
        pages: dict[str, str] = {}
        for item in data["results"]:
            if not isinstance(item, dict):
                raise WebSearchError("WEB_INVALID_RESPONSE", "正文提取结果条目无效。")
            url = public_web_url(item.get("url"))
            content = item.get("raw_content")
            if url in urls and isinstance(content, str) and content.strip():
                pages[url] = content.strip()[:MAX_PAGE_CHARS]
        return pages
