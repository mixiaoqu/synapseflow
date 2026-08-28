"""网页检索仅接收公开搜索目标和本地追踪标识。"""

from typing import Any, TypedDict

from app.agents.common.task_result import TaskResult
from app.services.web_search.schemas import WebPage


class WebSearchState(TypedDict, total=False):
    workflow_id: str
    run_id: str
    metadata: dict[str, Any]
    query: str
    pages: list[WebPage]
    extracted: dict[str, str]
    errors: list[dict[str, Any]]
    task_result: TaskResult
