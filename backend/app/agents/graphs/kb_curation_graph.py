"""Graph for admin-facing knowledge-base curation QA."""

from langgraph.graph import END, StateGraph

from app.agents.nodes.kb_curation import (
    answer_node,
    evaluate_node,
    query_optimizer_node,
    retrieve_node,
    should_continue_iteration,
)
from app.agents.states.kb_curation_state import KbCurationState


def create_kb_curation_graph():
    """Create the iterative graph used for admin knowledge curation."""
    workflow = StateGraph(KbCurationState)

    workflow.add_node("query_optimizer", query_optimizer_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("evaluate", evaluate_node)

    workflow.set_entry_point("query_optimizer")

    workflow.add_edge("query_optimizer", "retrieve")
    workflow.add_edge("retrieve", "answer")
    workflow.add_edge("answer", "evaluate")

    workflow.add_conditional_edges(
        "evaluate",
        should_continue_iteration,
        {
            "query_optimizer": "query_optimizer",
            "end": END,
        },
    )

    return workflow.compile()
