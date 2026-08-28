"""全局联网能力入口；Agent 不依赖具体提供方协议。"""

from app.core.config import settings
from app.services.web_search.schemas import WebSearchError, WebSearchGateway


def is_web_search_available() -> bool:
    return bool(settings.WEB_SEARCH_ENABLED and settings.TAVILY_API_KEY.strip())


def get_web_search_gateway() -> WebSearchGateway:
    if not is_web_search_available():
        raise WebSearchError("WEB_SEARCH_DISABLED", "联网搜索未启用或未配置密钥。")
    from app.services.web_search.tavily import TavilyGateway

    return TavilyGateway(api_key=settings.TAVILY_API_KEY.strip())
