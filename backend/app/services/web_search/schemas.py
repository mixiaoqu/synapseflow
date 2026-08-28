"""与搜索提供方无关的网页证据契约。"""

from ipaddress import ip_address
from typing import Protocol, TypedDict
from urllib.parse import urlsplit, urlunsplit

MAX_SEARCH_RESULTS = 5
MAX_EXTRACT_PAGES = 3
MAX_PAGE_CHARS = 8000
MAX_QUERY_CHARS = 500


class WebPage(TypedDict):
    url: str
    title: str
    snippet: str
    published_at: str | None
    fetched_at: str


class WebSearchError(ValueError):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class WebSearchGateway(Protocol):
    async def search(self, query: str) -> list[WebPage]: ...

    async def extract(self, urls: list[str]) -> dict[str, str]: ...


def public_web_url(value: object) -> str | None:
    """只接受公开 HTTP(S) 地址；本服务不直接访问网页或解析其 DNS。"""
    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    if any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not host:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if parsed.port not in {None, 80, 443}:
            return None
        if "." not in host or host.endswith((".localhost", ".local", ".internal")):
            return None
        try:
            if not ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return urlunsplit(parsed._replace(fragment=""))
    except ValueError:
        return None
