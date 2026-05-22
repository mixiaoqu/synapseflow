import importlib.util
import json

from app.agents.runtime import (
    AgentEventType,
    build_base_agent_context,
    build_graph,
    build_sse_envelope,
    get_graph_definition,
    merge_agent_state,
    render_sse_event,
)


def test_build_base_agent_context_includes_shared_fields():
    context = build_base_agent_context(
        user_id=1,
        team_id=2,
        knowledge_base_id=3,
        request_id="req-1",
        run_id="run-1",
        messages=[{"role": "user", "content": "hello"}],
        metadata={"workflow": "kb_chat"},
    )

    assert context["user_id"] == 1
    assert context["team_id"] == 2
    assert context["knowledge_base_id"] == 3
    assert context["request_id"] == "req-1"
    assert context["run_id"] == "run-1"
    assert context["messages"] == [{"role": "user", "content": "hello"}]
    assert context["metadata"] == {"workflow": "kb_chat"}


def test_merge_agent_state_preserves_context_and_extends_fields():
    context = build_base_agent_context(user_id=7, run_id="run-7")

    merged = merge_agent_state(context, {"query": "What is LangGraph?"})

    assert merged["user_id"] == 7
    assert merged["run_id"] == "run-7"
    assert merged["query"] == "What is LangGraph?"


def test_sse_envelope_uses_enum_values_and_renders_wire_format():
    envelope = build_sse_envelope(
        AgentEventType.START,
        {"message": "hello"},
        node_id="system",
        node_name="System",
        run_id="run-1",
        timestamp=123.45,
    )

    assert envelope["type"] == "start"
    payload = render_sse_event(envelope)
    assert payload.startswith("event: message\n")

    raw_json = payload.split("data: ", 1)[1].strip()
    parsed = json.loads(raw_json)
    assert parsed["type"] == "start"
    assert parsed["node_id"] == "system"
    assert parsed["run_id"] == "run-1"


def test_graph_registry_exposes_known_workflows():
    if importlib.util.find_spec("langgraph") is None:
        return

    assert get_graph_definition("kb_chat").node_ids == (
        "plan_query",
        "rewrite_query",
        "retrieve",
        "answer",
    )
    assert get_graph_definition("kb_chat_v2").node_ids == (
        "analyze",
        "rewrite_query",
        "retrieve",
        "evaluate",
        "answer",
    )

    compiled = build_graph("kb_chat")
    assert compiled is not None
    assert build_graph("kb_chat_v2") is not None
