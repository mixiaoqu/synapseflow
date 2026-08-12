"""Top-level Agent workflow graph."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.main.nodes import (
    aggregate_node,
    build_execute_node,
    build_plan_node,
    build_respond_node,
    build_route_node,
    build_understand_node,
)
from app.agents.main.state import AgentState
from app.agents.runtime.factory import get_graph_definition
from app.agents.runtime.handlers import get_handler_definitions


def create_agent_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Compile the single production/evaluation Agent workflow."""

    planner_factory = planner_llm_factory or llm_factory
    answer_factory = answer_llm_factory or llm_factory
    handlers = get_handler_definitions()
    handler_workflows = {
        handler.handler_id: get_graph_definition(handler.workflow_id).build(
            planner_llm_factory=planner_factory,
            answer_llm_factory=answer_factory,
        )
        for handler in handlers
    }
    workflow = StateGraph(AgentState)

    def after_understand(state: AgentState) -> str:
        understanding = state["understanding"]
        if (
            understanding["clarity"] != "clear"
            or understanding["handling"] != "delegated"
        ):
            return "respond"
        return "plan" if understanding["task_structure"] == "composite" else "route"

    workflow.add_node(
        "understand",
        build_understand_node(planner_llm_factory=planner_factory),
    )
    workflow.add_node("plan", build_plan_node(planner_llm_factory=planner_factory))
    workflow.add_node(
        "route",
        build_route_node(handlers=handlers, planner_llm_factory=planner_factory),
    )
    workflow.add_node(
        "execute",
        build_execute_node(handler_workflows=handler_workflows),
    )
    workflow.add_node("aggregate", aggregate_node)
    workflow.add_node("respond", build_respond_node(answer_llm_factory=answer_factory))
    workflow.set_entry_point("understand")
    workflow.add_conditional_edges(
        "understand",
        after_understand,
        {"plan": "plan", "route": "route", "respond": "respond"},
    )
    workflow.add_edge("plan", "route")
    workflow.add_edge("route", "execute")
    workflow.add_edge("execute", "aggregate")
    workflow.add_edge("aggregate", "respond")
    workflow.add_edge("respond", END)
    return workflow.compile()
