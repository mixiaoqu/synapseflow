from app.application.agent.workflow_meta import (
    build_node_summary,
    get_node_label,
    get_node_progress_message,
)


def test_workflow_meta_exposes_agent_node_progress_message():
    assert get_node_label("agent", "decide") == "规划下一步"
    assert get_node_progress_message("agent", "decide") == "正在结合目标与已有结果确定下一步..."


def test_workflow_meta_returns_empty_node_complete_payload():
    assert get_node_progress_message("agent", "unknown_node") == "正在处理..."
    assert build_node_summary("agent", "unknown_node", {"b": 1, "a": 2}) == {}


def test_activity_stage_identity_separates_parallel_calls_and_rounds():
    from app.application.agent.stream_adapter import AgentStreamAdapter
    from app.application.agent.workflow_meta import normalize_activity_payload

    payload = {
        "round": 2,
        "tool_call_id": "call_b",
        "display_stage": "execute",
        "activity_text": "查询中",
    }
    normalized = normalize_activity_payload(
        workflow_id="knowledge_qa",
        node_id="retrieve_knowledge",
        node_name="检索知识",
        payload=payload,
    )
    assert normalized["display_stage"] == "round_2:knowledge_search:call_b"
    assert normalized["display_title"] == "查阅资料"
    assert AgentStreamAdapter.execution_identity(normalized) == {
        "round": 2,
        "tool_call_id": "call_b",
    }
