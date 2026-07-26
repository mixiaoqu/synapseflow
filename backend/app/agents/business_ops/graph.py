"""Graph assembly for dynamically configured business tools."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.business_ops.nodes import build_business_ops_nodes
from app.agents.business_ops.state import BusinessOpsState
from app.application.business_operations import BusinessOperationService


def create_business_ops_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the dynamic business operations workflow graph."""

    del answer_llm_factory
    planner_factory = planner_llm_factory or llm_factory
    workflow = StateGraph(BusinessOpsState)
    nodes = build_business_ops_nodes(
        service=BusinessOperationService(),
        planner_factory=planner_factory,
    )

    workflow.add_node("analyze_request", nodes["analyze_request"])
    workflow.add_node("match_operation", nodes["match_operation"])
    workflow.add_node("execute_operation", nodes["execute_operation"])
    workflow.add_node("replan_operation_params", nodes["replan_operation_params"])
    workflow.add_node("compose_result", nodes["compose_result"])
    workflow.set_entry_point("analyze_request")
    workflow.add_conditional_edges(
        "analyze_request",
        nodes["route_after_analyze"],
        {"execute": "match_operation", "compose": "compose_result"},
    )
    workflow.add_edge("match_operation", "execute_operation")
    workflow.add_conditional_edges(
        "execute_operation",
        nodes["route_after_execute"],
        {
            "replan": "replan_operation_params",
            "analyze": "analyze_request",
            "compose": "compose_result",
        },
    )
    workflow.add_edge("replan_operation_params", "execute_operation")
    workflow.add_edge("compose_result", END)
    return workflow.compile()
