"""Graph for the v2 knowledge-base chat workflow."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.nodes.kb_chat_v2 import (
    build_kb_chat_v2_answer_node,
    kb_chat_v2_evaluate_node,
    kb_chat_v2_plan_query_node,
    kb_chat_v2_retrieve_node,
    kb_chat_v2_rewrite_query_node,
)
from app.agents.states import KbChatV2State


def _route_after_plan(state: KbChatV2State) -> str:
    return "answer" if state.get("retrieval_required") is False else "rewrite_query"


def create_kb_chat_v2_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    evaluator_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the v2 single-round graph used for KB chat."""

    planner_factory = planner_llm_factory or llm_factory
    answer_factory = answer_llm_factory or llm_factory
    workflow = StateGraph(KbChatV2State)

    async def _plan_node(state: KbChatV2State) -> dict[str, Any]:
        return await kb_chat_v2_plan_query_node(state, llm_factory=planner_factory)

    async def _evaluate_node(state: KbChatV2State) -> dict[str, Any]:
        return await kb_chat_v2_evaluate_node(state, llm_factory=evaluator_llm_factory)

    workflow.add_node("plan_query", _plan_node)
    workflow.add_node("rewrite_query", kb_chat_v2_rewrite_query_node)
    workflow.add_node("retrieve", kb_chat_v2_retrieve_node)
    workflow.add_node("evaluate", _evaluate_node)
    workflow.add_node("answer", build_kb_chat_v2_answer_node(llm_factory=answer_factory))
    workflow.set_entry_point("plan_query")
    workflow.add_conditional_edges(
        "plan_query",
        _route_after_plan,
        {"answer": "answer", "rewrite_query": "rewrite_query"},
    )
    workflow.add_edge("rewrite_query", "retrieve")
    workflow.add_edge("retrieve", "evaluate")
    workflow.add_edge("evaluate", "answer")
    workflow.add_edge("answer", END)
    return workflow.compile()
