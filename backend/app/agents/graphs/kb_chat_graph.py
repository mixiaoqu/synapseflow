"""Graph for end-user knowledge-base chat."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.nodes.kb_chat import (
    user_kb_retrieve_node,
)
from app.agents.nodes.kb_chat.generate_answer import build_user_kb_generate_answer_node
from app.agents.states.kb_chat_state import KbChatState


def create_kb_chat_graph(
    *,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the single-round graph used for user knowledge-base chat."""

    workflow = StateGraph(KbChatState)
    workflow.add_node("retrieve", user_kb_retrieve_node)
    workflow.add_node("answer", build_user_kb_generate_answer_node(llm_factory=llm_factory))
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "answer")
    workflow.add_edge("answer", END)
    return workflow.compile()
