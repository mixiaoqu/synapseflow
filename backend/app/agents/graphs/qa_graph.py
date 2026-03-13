"""迭代问答图"""
from langgraph.graph import StateGraph, END

from app.agents.states.qa_state import IterativeQAState
from app.agents.nodes.qa import (
    retrieve_node,
    answer_node,
    evaluate_node,
    should_continue_iteration,
)


def create_iterative_qa_graph():
    """创建迭代问答图"""
    workflow = StateGraph(IterativeQAState)

    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("evaluate", evaluate_node)

    workflow.set_entry_point("retrieve")

    workflow.add_edge("retrieve", "answer")
    workflow.add_edge("answer", "evaluate")

    workflow.add_conditional_edges(
        "evaluate",
        should_continue_iteration,
        {
            "retrieve": "retrieve",
            "end": END
        }
    )

    return workflow.compile()
