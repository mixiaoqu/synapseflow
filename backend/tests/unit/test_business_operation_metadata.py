from app.agents.graphs.business_ops_graph import _serialize_tool_candidates
from app.application.business_operations.registry import BusinessOperationRegistry
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
        input_schema={"type": "object", "properties": {}},
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

    candidate = _serialize_tool_candidates([record])[0]
    assert candidate["domain"] == "order"
    assert candidate["action"] == "query"
    assert candidate["read_only"] is True
    assert candidate["required_permissions"] == ["order:read"]
