import asyncio
import json
from time import monotonic

import httpx
import pytest

from app.agents.common.execution_budget import ExecutionBudget, execution_budget
from app.agents.main.result import aggregate_execution_results
from app.agents.runtime.tools import build_web_search_input, get_tool_definitions
from app.agents.web_search.graph import create_web_search_graph
from app.application.agent.run_trace import AgentRunTraceBuilder
from app.services.web_search import get_web_search_gateway, is_web_search_available, settings
from app.services.web_search.schemas import WebSearchError, public_web_url
from app.services.web_search.tavily import TavilyGateway


def page(url="https://example.com/guide", title="公开资料"):
    return {
        "url": url,
        "title": title,
        "snippet": "仅为搜索摘要",
        "published_at": None,
        "fetched_at": "2026-08-28T00:00:00+00:00",
    }


class FakeGateway:
    def __init__(self, pages=None, extracted=None, error=None):
        self.pages = [page()] if pages is None else pages
        self.extracted = (
            {self.pages[0]["url"]: "正文事实"}
            if extracted is None and self.pages
            else extracted or {}
        )
        self.error = error
        self.calls = []

    async def search(self, query):
        self.calls.append(("search", query))
        return self.pages

    async def extract(self, urls):
        self.calls.append(("extract", urls))
        if self.error:
            raise self.error
        return self.extracted


def run_graph(gateway):
    graph = create_web_search_graph(gateway_factory=lambda: gateway)
    return asyncio.run(
        graph.ainvoke(
            {
                "workflow_id": "web_search",
                "query": "公开资料",
                "run_id": "run1",
                "metadata": {"parent_task_id": "call1"},
            }
        )
    )["task_result"]


@pytest.mark.parametrize(
    "enabled,key,available",
    [
        (False, "", False),
        (False, "test-key", False),
        (True, " ", False),
        (True, "test-key", True),
    ],
)
def test_global_availability_is_independent_of_app(enabled, key, available, monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", enabled)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", key)
    tool = next(item for item in get_tool_definitions() if item.name == "search_web")
    assert is_web_search_available() is available
    assert tool.available({}) is available
    assert tool.available({"resources": {"project_app_id": 99}}) is available
    if not available:
        with pytest.raises(WebSearchError, match="未启用"):
            get_web_search_gateway()


def test_child_input_does_not_forward_private_context():
    result = build_web_search_input(
        {
            "input": {
                "run_id": "run1",
                "identity": {"user_id": 17},
                "conversation": {"history": [{"content": "private history"}]},
                "page_context": {"secret": "private record"},
                "metadata": {"token": "private-token"},
            }
        },
        {
            "call_id": "c1",
            "goal": "公开指南",
            "context": "private context",
            "dependency_results": {"c0": {"data": "private business data"}},
        },
    )
    assert result == {
        "workflow_id": "web_search",
        "run_id": "run1",
        "metadata": {"parent_task_id": "c1"},
        "query": "公开指南",
    }


def test_tavily_payload_limits_normalization_and_no_generated_answer():
    requests = []

    def handle(request):
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-secret"
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "answer": "不应进入证据的上游生成答案",
                    "results": [
                        {
                            "url": "https://example.com/guide#part",
                            "title": "公开指南",
                            "content": "摘要" * 2000,
                        },
                        {"url": "https://example.com/guide", "title": "重复页", "content": "重复"},
                        {"url": "http://127.0.0.1/private", "title": "私网"},
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {"url": "https://example.com/guide", "raw_content": "正文" * 10000},
                    {"url": "https://other.example/unrequested", "raw_content": "未请求的内容"},
                ]
            },
        )

    async def run():
        gateway = TavilyGateway(api_key="test-secret", transport=httpx.MockTransport(handle))
        pages = await gateway.search("公开指南")
        assert len(pages) == 1 and pages[0]["url"] == "https://example.com/guide"
        assert len(pages[0]["snippet"]) == 1500
        assert pages[0]["published_at"] is None and pages[0]["fetched_at"]
        extracted = await gateway.extract([pages[0]["url"]])
        assert list(extracted) == ["https://example.com/guide"]
        assert len(extracted[pages[0]["url"]]) == 8000

    asyncio.run(run())
    search_payload = json.loads(requests[0].content)
    assert search_payload == {
        "query": "公开指南",
        "search_depth": "basic",
        "topic": "general",
        "max_results": 5,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "auto_parameters": False,
    }
    assert json.loads(requests[1].content) == {
        "urls": ["https://example.com/guide"],
        "extract_depth": "basic",
        "format": "markdown",
        "timeout": 15,
    }
    assert all(request.url.host == "api.tavily.com" for request in requests)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "WEB_AUTH_ERROR"),
        (403, "WEB_AUTH_ERROR"),
        (429, "WEB_RATE_LIMIT"),
        (432, "WEB_RATE_LIMIT"),
        (433, "WEB_RATE_LIMIT"),
        (500, "WEB_UPSTREAM_ERROR"),
        (302, "WEB_HTTP_ERROR"),
        (400, "WEB_HTTP_ERROR"),
    ],
)
def test_upstream_failures_are_sanitized_without_retry(status, code):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, text="private key and upstream details")

    gateway = TavilyGateway(api_key="secret", transport=httpx.MockTransport(handle))
    with pytest.raises(WebSearchError) as error:
        asyncio.run(gateway.search("公开指南"))
    assert error.value.code == code
    assert "private" not in str(error.value) and "secret" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body,code",
    [
        (b"not json", "WEB_INVALID_RESPONSE"),
        (b'{"unexpected":[]}', "WEB_INVALID_RESPONSE"),
        (b'{"results":[1]}', "WEB_INVALID_RESPONSE"),
        pytest.param(b"x" * (1024 * 1024 + 1), "WEB_RESPONSE_TOO_LARGE", id="oversized"),
    ],
)
def test_invalid_or_oversized_response_is_not_a_no_hit(body, code):
    gateway = TavilyGateway(
        api_key="secret", transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    )
    with pytest.raises(WebSearchError) as error:
        asyncio.run(gateway.search("公开指南"))
    assert error.value.code == code


@pytest.mark.parametrize(
    "exception,code",
    [
        (httpx.ReadTimeout("private upstream details"), "WEB_TIMEOUT"),
        (httpx.ConnectError("private upstream details"), "WEB_NETWORK_ERROR"),
    ],
)
def test_network_failure_and_timeout(exception, code):
    def handle(_):
        raise exception

    gateway = TavilyGateway(api_key="secret", transport=httpx.MockTransport(handle))
    with pytest.raises(WebSearchError) as error:
        asyncio.run(gateway.search("公开指南"))
    assert error.value.code == code and error.value.retryable
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://localhost/a",
        "http://127.0.0.1/a",
        "http://192.168.0.1/a",
        "http://[::1]/a",
        "https://u:p@example.com/a",
        "https://example.com:8080/a",
        "https://example.com/\\evil",
        "https://internal.local/a",
        "https://example.com/\n",
    ],
)
def test_reject_nonpublic_or_unsafe_urls(url):
    assert public_web_url(url) is None


def test_gateway_parameter_validation_precedes_http():
    def handle(_):
        pytest.fail("invalid parameters must not reach HTTP")

    gateway = TavilyGateway(api_key="secret", transport=httpx.MockTransport(handle))
    for query in ["", "x" * 501]:
        with pytest.raises(WebSearchError):
            asyncio.run(gateway.search(query))
    for urls in [[], ["http://127.0.0.1/a"], ["https://example.com/a"] * 4]:
        with pytest.raises(WebSearchError):
            asyncio.run(gateway.extract(urls))


def test_empty_search_skips_extract_and_reports_no_hits():
    gateway = FakeGateway(pages=[])
    result = run_graph(gateway)
    assert len(gateway.calls) == 1
    assert result["data"]["normalized"]["retrieval_status"] == "no_hits"
    assert result["status"] == "failed" and not result["errors"]


def test_partial_extraction_keeps_snippet_separate_from_citations():
    gateway = FakeGateway(pages=[page(), page("https://example.com/other")])
    result = run_graph(gateway)
    assert result["status"] == "partial_success"
    evidence = result["data"]["content"]["web_context"]
    assert evidence[0]["source"]["content_scope"] == "excerpt"
    assert evidence[1]["role"] == "supporting"
    assert evidence[1]["source"]["content_scope"] == "search_snippet"
    assert len(result["evidence"]["citations"]) == 1
    assert result["errors"][0]["code"] == "WEB_EXTRACT_INCOMPLETE"


def test_failed_extraction_is_not_presented_as_verified_evidence():
    result = run_graph(FakeGateway(error=WebSearchError("WEB_TIMEOUT", "请求超时")))
    assert result["status"] == "failed"
    assert result["evidence"]["citations"] == []
    assert result["data"]["content"]["web_context"][0]["source"]["extraction_status"] == "failed"


def test_web_sources_do_not_become_knowledge_documents_or_vector_hits():
    task_result = run_graph(FakeGateway())
    run = {"call_id": "c1", "goal": "公开资料", "task_result": task_result}
    aggregate = aggregate_execution_results({"c1": run})
    assert aggregate["knowledge_context"] == []
    metadata = aggregate["sources"][0]["metadata"]
    assert metadata["source_type"] == "web" and metadata["url"] == page()["url"]
    assert not any(key.startswith("document_") for key in metadata)
    trace = AgentRunTraceBuilder.build_log_trace_payload(
        state={}, result=aggregate, retrieved_docs=aggregate["sources"]
    )
    assert trace["web_sources"] == aggregate["sources"]
    assert trace["final_context_docs"] == []
    assert trace["source_summary"]["vector"]["candidate_count"] == 0


def test_workflow_limits_extract_pages_and_counts_shared_budget():
    gateway = FakeGateway(pages=[page(f"https://example.com/{i}") for i in range(5)])
    budget = ExecutionBudget(limit=2, deadline=monotonic() + 10)
    with execution_budget(budget):
        run_graph(gateway)
    assert budget.used == 2
    assert len(gateway.calls[1][1]) == 3


def test_custom_progress_includes_registered_web_workflow():
    async def run():
        graph = create_web_search_graph(gateway_factory=lambda: FakeGateway())
        return [event async for event in graph.astream({"query": "公开资料"}, stream_mode="custom")]

    events = asyncio.run(run())
    assert [event["node_id"] for event in events] == ["search", "extract"]
    assert all(event["workflow_id"] == "web_search" for event in events)


def test_later_success_can_replace_earlier_snippet_for_same_url():
    failed = run_graph(FakeGateway(extracted={}))
    successful = run_graph(FakeGateway())
    result = aggregate_execution_results(
        {
            "c1": {"call_id": "c1", "goal": "公开资料", "task_result": failed},
            "c2": {"call_id": "c2", "goal": "核实正文", "task_result": successful},
        }
    )
    assert len(result["sources"]) == 1
    assert result["sources"][0]["content"] == "正文事实"


def test_disabled_direct_graph_fails_without_http(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", False)
    result = asyncio.run(create_web_search_graph().ainvoke({"query": "公开资料"}))
    assert result["task_result"]["status"] == "failed"
    assert result["task_result"]["errors"][0]["code"] == "WEB_SEARCH_DISABLED"


def test_web_citations_survive_widget_and_remote_mcp_contracts(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.api import mcp_server as mcp_module
    from app.application.agent.stream_adapter import AgentStreamAdapter

    task_result = run_graph(FakeGateway())
    result = aggregate_execution_results(
        {"c1": {"call_id": "c1", "goal": "公开资料", "task_result": task_result}}
    )
    payload = AgentStreamAdapter.complete_payload(
        response={"answer": "结果", "status": "answered", "sources": result["sources"]},
        assistant_id=None,
        assistant_name=None,
        session_id=None,
        log_id=None,
    )
    assert payload["retrieved_docs"] == result["sources"]
    monkeypatch.setattr(mcp_module, "_current_context", lambda: object())
    monkeypatch.setattr(
        mcp_module,
        "chat_remote_mcp",
        AsyncMock(
            return_value=SimpleNamespace(
                answer="结果",
                answer_status="answered",
                retrieved_docs=result["sources"],
            )
        ),
    )
    response = asyncio.run(mcp_module.agent_chat("公开资料"))
    source = response["sources"][0]
    assert source["url"] == page()["url"] and source["source_type"] == "web"
    assert source["document_id"] is None
    assert source["content_scope"] == "excerpt" and source["fetched_at"]
