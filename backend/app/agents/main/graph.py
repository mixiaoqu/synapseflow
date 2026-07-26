"""Top-level Agent workflow graph."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.main.nodes import (
    EXECUTION_ROUTE_TYPES,
    aggregate_node,
    build_execute_node,
    build_plan_node,
    build_respond_node,
    build_route_node,
)
from app.agents.main.state import AgentState
from app.agents.runtime.factory import get_graph_definition
from app.agents.runtime.sub_agents import get_sub_agent_definitions


def create_agent_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Compile the single production/evaluation Agent workflow."""

    planner_factory = planner_llm_factory or llm_factory
    answer_factory = answer_llm_factory or llm_factory
    sub_agents = get_sub_agent_definitions()
    sub_agent_graphs = {
        item.sub_agent_id: get_graph_definition(item.graph_id).build(
            planner_llm_factory=planner_factory,
            answer_llm_factory=answer_factory,
        )
        for item in sub_agents
    }
    workflow = StateGraph(AgentState)

    def after_route(state: AgentState) -> str:
        return (
            "plan"
            if state["routing"]["route_type"] in EXECUTION_ROUTE_TYPES
            else "respond"
        )

    workflow.add_node(
        "route",
        build_route_node(
            sub_agents=sub_agents,
            planner_llm_factory=planner_factory,
        ),
    )
    workflow.add_node("plan", build_plan_node(planner_llm_factory=planner_factory))
    workflow.add_node("execute", build_execute_node(sub_agent_graphs=sub_agent_graphs))
    workflow.add_node("aggregate", aggregate_node)
    workflow.add_node("respond", build_respond_node(answer_llm_factory=answer_factory))
    workflow.set_entry_point("route")
    workflow.add_conditional_edges(
        "route",
        after_route,
        {"plan": "plan", "respond": "respond"},
    )
    workflow.add_edge("plan", "execute")
    workflow.add_edge("execute", "aggregate")
    workflow.add_edge("aggregate", "respond")
    workflow.add_edge("respond", END)
    return workflow.compile()
