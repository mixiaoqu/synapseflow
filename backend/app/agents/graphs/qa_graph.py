"""迭代问答图

方案A 平铺节点流程：
  [提问优化] -> retrieve -> answer -> evaluate
       ^                                      |
       +------------------[继续迭代]-----------+
"""
from langgraph.graph import StateGraph, END

from app.agents.states.qa_state import IterativeQAState
from app.agents.nodes.qa import (
    query_optimizer_node,
    retrieve_node,
    answer_node,
    evaluate_node,
    should_continue_iteration,
)


def create_iterative_qa_graph():
    """创建迭代问答图"""
    workflow = StateGraph(IterativeQAState)

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
        }
    )

    return workflow.compile()
