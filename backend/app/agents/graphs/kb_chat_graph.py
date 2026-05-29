"""Graph for the knowledge-base chat workflow."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.nodes.kb_chat import (
    build_kb_chat_answer_node,
    kb_chat_analyze_node,
    kb_chat_evaluate_node,
    kb_chat_retrieve_node,
    kb_chat_rewrite_query_node,
)
from app.agents.states import KbChatState


def _route_after_analyze(state: KbChatState) -> str:
    return "answer" if str(state.get("retrieval_strategy") or "").strip().lower() == "skip" else "rewrite_query"


def create_kb_chat_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    evaluator_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the single knowledge-base chat graph."""

    planner_factory = planner_llm_factory or llm_factory
    answer_factory = answer_llm_factory or llm_factory
    workflow = StateGraph(KbChatState)

    async def _analyze_node(state: KbChatState) -> dict[str, Any]:
        return await kb_chat_analyze_node(state, llm_factory=planner_factory)

    async def _evaluate_node(state: KbChatState) -> dict[str, Any]:
        return await kb_chat_evaluate_node(state, llm_factory=evaluator_llm_factory)

    workflow.add_node("analyze", _analyze_node)
    workflow.add_node("rewrite_query", kb_chat_rewrite_query_node)
    workflow.add_node("retrieve", kb_chat_retrieve_node)
    workflow.add_node("evaluate", _evaluate_node)
    workflow.add_node("answer", build_kb_chat_answer_node(llm_factory=answer_factory))
    workflow.set_entry_point("analyze")
    workflow.add_conditional_edges(
        "analyze",
        _route_after_analyze,
        {"answer": "answer", "rewrite_query": "rewrite_query"},
    )
    workflow.add_edge("rewrite_query", "retrieve")
    workflow.add_edge("retrieve", "evaluate")
    workflow.add_edge("evaluate", "answer")
    workflow.add_edge("answer", END)
    return workflow.compile()
