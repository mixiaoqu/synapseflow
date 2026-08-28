"""基于能力工具反馈的主 Agent。"""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.common.execution_budget import AgentLimits
from app.agents.main.nodes import build_decide_node, build_execute_node, build_respond_node
from app.agents.main.state import AgentState
from app.agents.runtime.factory import get_graph_definition
from app.agents.runtime.tools import AgentToolDefinition, get_tool_definitions


def create_agent_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
    tools: tuple[AgentToolDefinition, ...] | None = None,
    tool_workflows: dict[str, Any] | None = None,
    limits: AgentLimits | None = None,
):
    planner_factory = planner_llm_factory or llm_factory
    answer_factory = answer_llm_factory or llm_factory
    definitions = get_tool_definitions() if tools is None else tools
    if len({tool.name for tool in definitions}) != len(definitions):
        raise ValueError("内置工具名称必须唯一")
    workflows = (
        tool_workflows
        if tool_workflows is not None
        else {
            tool.name: get_graph_definition(tool.workflow_id).build(
                planner_llm_factory=planner_factory,
                answer_llm_factory=answer_factory,
            )
            for tool in definitions
        }
    )
    if set(workflows) != {tool.name for tool in definitions}:
        raise ValueError("能力工具与执行实现必须一一对应")
    policy = limits or AgentLimits()
    graph = StateGraph(AgentState)
    graph.add_node(
        "decide",
        build_decide_node(
            tools=definitions,
            planner_llm_factory=planner_factory,
            limits=policy,
        ),
    )
    graph.add_node(
        "execute",
        build_execute_node(
            tools=definitions,
            tool_workflows=workflows,
            limits=policy,
        ),
    )
    graph.add_node(
        "respond",
        build_respond_node(answer_llm_factory=answer_factory, timeout=policy.model_timeout),
    )
    graph.set_entry_point("decide")
    graph.add_conditional_edges(
        "decide",
        lambda state: "execute" if state.get("pending_calls") else "respond",
        {"execute": "execute", "respond": "respond"},
    )
    graph.add_edge("execute", "decide")
    graph.add_edge("respond", END)
    return graph.compile()
