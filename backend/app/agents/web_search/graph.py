"""确定性的搜索、正文提取、证据整理；不增加规划模型调用。"""

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.common.execution_budget import consume_operation
from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.common.task_result import build_task_result
from app.agents.web_search.state import WebSearchState
from app.services.web_search import get_web_search_gateway
from app.services.web_search.schemas import MAX_EXTRACT_PAGES, WebSearchError, WebSearchGateway


def _activity(node_id: str, message: str) -> None:
    emit_progress(
        get_optional_stream_writer(),
        workflow_id="web_search",
        node_id=node_id,
        message=message,
        stage="start",
        activity_text=message,
    )


def _error(exc: WebSearchError) -> dict[str, Any]:
    return {"code": exc.code, "message": str(exc), "retryable": exc.retryable, "details": {}}


def create_web_search_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    gateway_factory: Callable[[], WebSearchGateway] = get_web_search_gateway,
):
    async def search(state: WebSearchState) -> dict[str, Any]:
        _activity("search", "正在搜索公开网页...")
        try:
            gateway = gateway_factory()
            consume_operation()
            pages = await gateway.search(state["query"])
            return {"pages": pages[:MAX_EXTRACT_PAGES], "extracted": {}, "errors": []}
        except WebSearchError as exc:
            return {"pages": [], "extracted": {}, "errors": [_error(exc)]}

    async def extract(state: WebSearchState) -> dict[str, Any]:
        _activity("extract", "正在提取搜索结果正文...")
        try:
            gateway = gateway_factory()
            consume_operation()
            extracted = await gateway.extract([page["url"] for page in state["pages"]])
            errors = []
            if len(extracted) < len(state["pages"]):
                errors = [
                    _error(
                        WebSearchError(
                            "WEB_EXTRACT_INCOMPLETE", "部分网页未获得正文，摘要仅作为检索线索。"
                        )
                    )
                ]
            return {"extracted": extracted, "errors": errors}
        except WebSearchError as exc:
            return {"extracted": {}, "errors": [_error(exc)]}

    def compose_result(state: WebSearchState) -> dict[str, Any]:
        pages = state.get("pages") or []
        extracted = state.get("extracted") or {}
        errors = state.get("errors") or []
        usable = sum(bool(extracted.get(page["url"])) for page in pages)
        status = (
            "success"
            if usable == len(pages) and usable
            else "partial_success" if usable else "failed"
        )
        retrieval_status = "found" if usable else "provider_error" if errors else "no_hits"
        message = (
            f"已提取 {usable} 个网页的正文节选。"
            if usable
            else (
                "未获得可核验的网页正文，不能据此确认事实。"
                if errors
                else "搜索未找到可用的公开网页。"
            )
        )
        result = build_task_result(
            dict(state),
            handler_id="web_search",
            status=status,
            answer_status=(
                "answered" if status == "success" else "partial" if usable else "no_answer"
            ),
            title="联网检索结果",
            message=message,
        )
        evidence = []
        for page in pages:
            body = extracted.get(page["url"], "")
            evidence.append(
                {
                    "ref_id": "web:" + sha256(page["url"].encode()).hexdigest()[:20],
                    "role": "primary" if body else "supporting",
                    "kind": "web_page" if body else "web_snippet",
                    "content": body or page["snippet"],
                    "source": {
                        "source_type": "web",
                        "url": page["url"],
                        "title": page["title"],
                        "published_at": page["published_at"],
                        "fetched_at": (
                            datetime.now(timezone.utc).isoformat() if body else page["fetched_at"]
                        ),
                        "extraction_status": "extracted" if body else "failed",
                        "content_scope": "excerpt" if body else "search_snippet",
                    },
                }
            )
        result["data"] = {
            "kind": "web",
            "content": {"web_context": evidence},
            "normalized": {"retrieval_status": retrieval_status, "extracted_count": usable},
        }
        result["evidence"] = {
            "citations": [
                {"ref_id": item["ref_id"], **item["source"]}
                for item in evidence
                if item["role"] == "primary"
            ]
        }
        result["errors"] = errors
        return {"task_result": result}

    graph = StateGraph(WebSearchState)
    graph.add_node("search", search)
    graph.add_node("extract", extract)
    graph.add_node("compose_result", compose_result)
    graph.set_entry_point("search")
    graph.add_conditional_edges(
        "search",
        lambda state: "extract" if state.get("pages") else "compose_result",
        {"extract": "extract", "compose_result": "compose_result"},
    )
    graph.add_edge("extract", "compose_result")
    graph.add_edge("compose_result", END)
    return graph.compile()
