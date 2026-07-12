from app.application.workflow_meta import (
    build_node_summary,
    get_node_label,
    get_node_progress_message,
)


def test_workflow_meta_exposes_agent_node_progress_message():
    assert get_node_label("agent", "classify") == "识别任务"
    assert get_node_progress_message("agent", "classify") == "正在识别任务类型..."


def test_workflow_meta_returns_empty_node_complete_payload():
    assert get_node_progress_message("agent", "unknown_node") == "正在处理..."
    assert build_node_summary("agent", "unknown_node", {"b": 1, "a": 2}) == {}
