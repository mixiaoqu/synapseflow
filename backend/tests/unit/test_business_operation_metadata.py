import json
from types import SimpleNamespace

import pytest

import app.agents.business_ops.decision as business_ops_decision
import app.agents.business_ops.graph as business_ops_graph
from app.agents.business_ops.decision import serialize_tool_candidates
from app.agents.business_ops.tools.execution import build_tool_step
from app.agents.business_ops.tools.results import build_tool_run_result
from app.agents.business_ops.tools.schemas import ToolDecision, ToolStep
from app.application.business_operations.registry import BusinessOperationRegistry
from app.application.business_operations.schemas import BusinessOperationResult
from app.db.models import AgentTool, ToolProvider
from app.repositories.agent_tool_repository import AgentToolExecutionRecord


def _record():
    tool = AgentTool(
        tool_key="medical_center_query_orders",
        name="查询订单",
        agent_description="查询当前门店订单",
        external_name="query_orders",
        external_display_name="业务端订单查询",
        external_description="业务端描述",
        domain="order",
        action="query",
        read_only=True,
        required_permissions=["order:read"],
        input_schema={
            "type": "object",
            "properties": {"order_number": {"type": "string"}},
            "additionalProperties": False,
        },
        required_context=["store_id", "external_user_id"],
        risk_level="low",
        requires_confirmation=False,
    )
    provider = ToolProvider(
        code="medical_center",
        name="医疗中心",
        base_url="https://example.test/agent-tools",
        transport_type="business_http",
        auth_type="none",
    )
    return AgentToolExecutionRecord(tool=tool, provider=provider)


def test_runtime_definition_and_candidate_include_source_metadata():
    record = _record()

    operation = BusinessOperationRegistry.from_tool_record(record)
    assert operation.domain == "order"
    assert operation.action == "query"
    assert operation.read_only is True
    assert operation.required_permissions == ["order:read"]

    candidate = serialize_tool_candidates(
        [BusinessOperationRegistry().from_tool_record(record)]
    )[0]
    assert candidate["domain"] == "order"
    assert candidate["action"] == "query"
    assert candidate["read_only"] is True
    assert candidate["required_permissions"] == ["order:read"]


def test_business_request_accepts_current_call_action():
    candidates = serialize_tool_candidates(
        [BusinessOperationRegistry().from_tool_record(_record())]
    )

    request = business_ops_decision.normalize_business_request(
        {
            "action": "call_tool",
            "tool_id": "medical_center_query_orders",
            "arguments": {},
            "reason": "查询订单",
        },
        query="先查订单再查详情",
        candidates=candidates,
        call_history=[],
    )

    assert business_ops_decision.MAX_BUSINESS_TOOL_CALLS == 3
    assert request["status"] == "ready"
    assert request["operation_id"] == "medical_center_query_orders"


def test_business_request_prompt_redecides_after_each_call():
    prompt = business_ops_decision.build_business_request_analysis_prompt(
        "查询最新订单",
        serialize_tool_candidates(
            [BusinessOperationRegistry().from_tool_record(_record())]
        ),
        {},
        [],
    )

    assert "已有调用结果足以回答用户问题时必须返回 complete" in prompt
    assert "每次只选择一个工具" in prompt
    assert "needs_follow_up" not in prompt


def test_business_request_rejects_duplicate_serial_call():
    candidates = serialize_tool_candidates(
        [BusinessOperationRegistry().from_tool_record(_record())]
    )

    request = business_ops_decision.normalize_business_request(
        {
            "action": "call_tool",
            "tool_id": "medical_center_query_orders",
            "arguments": {},
            "reason": "继续查询",
        },
        query="继续查询",
        candidates=candidates,
        call_history=[
            {
                "tool_id": "medical_center_query_orders",
                "arguments": {},
                "status": "success",
                "data": {"items": []},
            }
        ],
    )

    assert request["status"] == "unsupported"
    assert "重复" in request["reason"]


def test_combined_business_result_preserves_ordered_calls():
    history = [
        {"tool_id": "sales_2024", "arguments": {}, "status": "success", "data": {"sales": 10}},
        {"tool_id": "sales_2025", "arguments": {}, "status": "success", "data": {"sales": 20}},
    ]

    result = business_ops_decision.build_combined_business_result(history)

    assert [item["operation_id"] for item in result["tool_calls"]] == ["sales_2024", "sales_2025"]
    assert result["tool_calls"][1]["data"]["sales"] == 20


@pytest.mark.asyncio
async def test_business_ops_graph_executes_two_read_only_calls_in_order(monkeypatch):
    record = _record()

    class FakeService:
        async def get_tool_availability_snapshot(self, project_app_id):
            return {
                "tool_grant_count": 1,
                "available_tool_keys": [record.tool.tool_key],
                "unavailable_reason_counts": {},
            }

        async def list_available_operations(self, project_app_id):
            return [BusinessOperationRegistry().from_tool_record(record)]

        async def execute(self, request):
            return BusinessOperationResult(
                success=True,
                operation_id=request.operation_id,
                message="查询成功",
                data={"order_number": request.params["order_number"]},
            )

    class FakePlanner:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, prompt):
            self.calls += 1
            if self.calls == 3:
                return SimpleNamespace(
                    content=json.dumps(
                        {"action": "complete", "reason": "两张订单均已查询"},
                        ensure_ascii=False,
                    )
                )
            order_number = "A1001" if self.calls == 1 else "A1002"
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "action": "call_tool",
                        "tool_id": record.tool.tool_key,
                        "arguments": {"order_number": order_number},
                        "reason": "按顺序查询",
                    },
                    ensure_ascii=False,
                )
            )

    planner = FakePlanner()
    monkeypatch.setattr(business_ops_graph, "BusinessOperationService", FakeService)
    graph = business_ops_graph.create_business_ops_graph(planner_llm_factory=lambda: planner)

    result = await graph.ainvoke(
        {
            "query": "依次查询两张订单",
            "project_app_id": 1,
            "external_user_id": "user-1",
            "store_id": "store-1",
            "dependency_results": {},
        }
    )

    assert result["business_call_count"] == 2
    assert [item["data"]["order_number"] for item in result["business_result"]["tool_calls"]] == [
        "A1001",
        "A1002",
    ]
    assert result["sub_agent_result"]["status"] == "success"


def test_tool_run_result_is_partial_when_a_later_step_fails():
    result = build_tool_run_result(
        decision=ToolDecision(action="unsupported", reason="详情查询失败"),
        steps=[
            ToolStep(
                index=1,
                tool_id="query_orders",
                arguments={},
                status="success",
                data={"items": [{"order_number": "A1001"}]},
            ),
            ToolStep(
                index=2,
                tool_id="get_order_detail",
                arguments={"order_number": "A1001"},
                status="failed",
                error={"code": "UPSTREAM_ERROR", "message": "详情服务不可用"},
            ),
        ],
    )

    assert result.status == "partial_success"
    assert len(result.successful_data) == 1


def test_build_tool_step_preserves_an_individual_failure():
    step = build_tool_step(
        index=2,
        tool_id="get_order_detail",
        arguments={"order_number": "A1001"},
        result=BusinessOperationResult(
            success=False,
            operation_id="get_order_detail",
            message="详情服务不可用",
            error={"code": "UPSTREAM_ERROR", "message": "详情服务不可用"},
            duration_ms=120,
        ),
    )

    assert step.status == "failed"
    assert step.error is not None
    assert step.error.code == "UPSTREAM_ERROR"
    assert step.duration_ms == 120


@pytest.mark.asyncio
async def test_business_ops_redecides_after_each_success_without_follow_up_flag(monkeypatch):
    record = _record()

    class FakeService:
        async def get_tool_availability_snapshot(self, project_app_id):
            return {
                "tool_grant_count": 1,
                "available_tool_keys": [record.tool.tool_key],
                "unavailable_reason_counts": {},
            }

        async def list_available_operations(self, project_app_id):
            return [BusinessOperationRegistry().from_tool_record(record)]

        async def execute(self, request):
            return BusinessOperationResult(
                success=True,
                operation_id=request.operation_id,
                message="查询成功",
                data={"order_number": request.params["order_number"]},
            )

    responses = [
        {
            "action": "call_tool",
            "tool_id": record.tool.tool_key,
            "arguments": {"order_number": "A1001"},
            "reason": "先查询订单",
        },
        {"action": "complete", "reason": "已有结果足以回答"},
    ]

    class FakePlanner:
        async def ainvoke(self, prompt):
            return SimpleNamespace(content=json.dumps(responses.pop(0), ensure_ascii=False))

    monkeypatch.setattr(business_ops_graph, "BusinessOperationService", FakeService)
    graph = business_ops_graph.create_business_ops_graph(planner_llm_factory=FakePlanner)
    result = await graph.ainvoke(
        {
            "query": "查询订单 A1001",
            "project_app_id": 1,
            "dependency_results": {},
        }
    )

    assert result["business_call_count"] == 1
    assert result["sub_agent_result"]["status"] == "success"
    assert responses == []


@pytest.mark.asyncio
async def test_business_ops_stops_before_a_fourth_tool_call(monkeypatch):
    record = _record()

    class FakeService:
        def __init__(self):
            self.executions = 0

        async def get_tool_availability_snapshot(self, project_app_id):
            return {
                "tool_grant_count": 1,
                "available_tool_keys": [record.tool.tool_key],
                "unavailable_reason_counts": {},
            }

        async def list_available_operations(self, project_app_id):
            return [BusinessOperationRegistry().from_tool_record(record)]

        async def execute(self, request):
            self.executions += 1
            return BusinessOperationResult(
                success=True,
                operation_id=request.operation_id,
                message="查询成功",
                data={"order_number": request.params["order_number"]},
            )

    service = FakeService()

    class FakePlanner:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, prompt):
            self.calls += 1
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "action": "call_tool",
                        "tool_id": record.tool.tool_key,
                        "arguments": {"order_number": f"A100{self.calls}"},
                        "reason": "继续查询",
                    },
                    ensure_ascii=False,
                )
            )

    planner = FakePlanner()
    monkeypatch.setattr(business_ops_graph, "BusinessOperationService", lambda: service)
    graph = business_ops_graph.create_business_ops_graph(planner_llm_factory=lambda: planner)
    result = await graph.ainvoke(
        {"query": "连续查询订单", "project_app_id": 1, "dependency_results": {}}
    )

    assert service.executions == 3
    assert result["business_call_count"] == 3
    assert result["sub_agent_result"]["status"] == "limit_reached"


@pytest.mark.asyncio
async def test_business_ops_reports_partial_success_after_a_later_failure(monkeypatch):
    record = _record()

    class FakeService:
        def __init__(self):
            self.executions = 0

        async def get_tool_availability_snapshot(self, project_app_id):
            return {
                "tool_grant_count": 1,
                "available_tool_keys": [record.tool.tool_key],
                "unavailable_reason_counts": {},
            }

        async def list_available_operations(self, project_app_id):
            return [BusinessOperationRegistry().from_tool_record(record)]

        async def execute(self, request):
            self.executions += 1
            if self.executions == 1:
                return BusinessOperationResult(
                    success=True,
                    operation_id=request.operation_id,
                    message="查询成功",
                    data={"order_number": "A1001"},
                )
            return BusinessOperationResult(
                success=False,
                operation_id=request.operation_id,
                message="详情服务不可用",
                error={"code": "UPSTREAM_ERROR", "message": "详情服务不可用"},
            )

    responses = [
        {
            "action": "call_tool",
            "tool_id": record.tool.tool_key,
            "arguments": {"order_number": "A1001"},
        },
        {
            "action": "call_tool",
            "tool_id": record.tool.tool_key,
            "arguments": {"order_number": "A1002"},
        },
    ]

    class FakePlanner:
        async def ainvoke(self, prompt):
            return SimpleNamespace(content=json.dumps(responses.pop(0), ensure_ascii=False))

    monkeypatch.setattr(business_ops_graph, "BusinessOperationService", FakeService)
    graph = business_ops_graph.create_business_ops_graph(planner_llm_factory=FakePlanner)
    result = await graph.ainvoke(
        {"query": "查询两张订单", "project_app_id": 1, "dependency_results": {}}
    )

    assert [step["status"] for step in result["business_call_history"]] == ["success", "failed"]
    assert result["sub_agent_result"]["status"] == "partial_success"
    assert result["sub_agent_result"]["answer_status"] == "partial"
