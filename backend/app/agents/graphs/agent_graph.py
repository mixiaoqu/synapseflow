"""Top-level enterprise orchestration agent workflow graph."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.nodes.agent_orchestration import (
    EXECUTION_ROUTE_TYPES,
    build_classify_node,
    build_dispatch_node,
    build_respond_node,
    build_route_node,
    collect_node,
    intake_node,
    orchestrate_plan_node,
    synthesize_node,
)
from app.agents.runtime.factory import get_graph_definition
from app.agents.runtime.sub_agents import get_sub_agent_definitions
from app.agents.states import AgentState


def create_agent_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the top-level enterprise orchestration workflow graph."""

    planner_factory = planner_llm_factory or llm_factory
    answer_factory = answer_llm_factory or llm_factory
    sub_agents = get_sub_agent_definitions()
    sub_agent_graphs = {
        sub_agent.sub_agent_id: get_graph_definition(sub_agent.graph_id).build(
            planner_llm_factory=planner_factory,
            answer_llm_factory=answer_factory,
        )
        for sub_agent in sub_agents
    }
    available_sub_agent_ids = {sub_agent.sub_agent_id for sub_agent in sub_agents}
    workflow = StateGraph(AgentState)

    def route_after_route(state: AgentState) -> str:
        route_type = str((state.get("route") or {}).get("route_type") or "").strip()
        if route_type in EXECUTION_ROUTE_TYPES:
            return "orchestrate_plan"
        return "respond"

    workflow.add_node("intake", intake_node)
    workflow.add_node(
        "classify",
        build_classify_node(
            sub_agents=sub_agents,
            planner_llm_factory=planner_factory,
        ),
    )
    workflow.add_node(
        "route",
        build_route_node(available_sub_agent_ids=available_sub_agent_ids),
    )
    workflow.add_node("orchestrate_plan", orchestrate_plan_node)
    workflow.add_node("dispatch", build_dispatch_node(sub_agent_graphs=sub_agent_graphs))
    workflow.add_node("collect", collect_node)
    workflow.add_node("synthesize", synthesize_node)
    workflow.add_node("respond", build_respond_node(answer_llm_factory=answer_factory))
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "classify")
    workflow.add_edge("classify", "route")
    workflow.add_conditional_edges(
        "route",
        route_after_route,
        {"orchestrate_plan": "orchestrate_plan", "respond": "respond"},
    )
    workflow.add_edge("orchestrate_plan", "dispatch")
    workflow.add_edge("dispatch", "collect")
    workflow.add_edge("collect", "synthesize")
    workflow.add_edge("synthesize", "respond")
    workflow.add_edge("respond", END)
    return workflow.compile()
