"""知识库单轮问答图（面向最终用户）

流程：用户检索 → 用户向生成答案 → 结束。
节点位于 agents/nodes/kb_user_qa/，与迭代 QA（qa/）分离。
"""
from langgraph.graph import StateGraph, END

from app.agents.states.kb_user_qa_state import KbUserQAState
from app.agents.nodes.kb_user_qa import (
    user_kb_retrieve_node,
    user_kb_generate_answer_node,
)


def create_kb_simple_qa_graph():
    workflow = StateGraph(KbUserQAState)
    workflow.add_node("retrieve", user_kb_retrieve_node)
    workflow.add_node("answer", user_kb_generate_answer_node)
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "answer")
    workflow.add_edge("answer", END)
    return workflow.compile()
