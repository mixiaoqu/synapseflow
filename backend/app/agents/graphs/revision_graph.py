"""递归修订图"""
from langgraph.graph import StateGraph, END

from app.agents.states.revision_state import RecursiveRevisionState
from app.agents.nodes.revision import (
    analyze_structure_node,
    detect_missing_node,
    revise_node,
    validate_node,
    should_continue_revision,
)


def create_recursive_revision_graph():
    """创建递归修订图"""
    workflow = StateGraph(RecursiveRevisionState)

    workflow.add_node("analyze_structure", analyze_structure_node)
    workflow.add_node("detect_missing", detect_missing_node)
    workflow.add_node("revise", revise_node)
    workflow.add_node("validate", validate_node)

    workflow.set_entry_point("analyze_structure")

    workflow.add_edge("analyze_structure", "detect_missing")
    workflow.add_edge("detect_missing", "revise")
    workflow.add_edge("revise", "validate")

    workflow.add_conditional_edges(
        "validate",
        should_continue_revision,
        {
            "detect_missing": "detect_missing",
            "end": END
        }
    )

    return workflow.compile()
