"""Centralized graph registry for SynapseFlow workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class GraphDefinition:
    """Metadata for a compiled graph factory."""

    graph_id: str
    factory: Callable[..., Any]
    node_ids: tuple[str, ...]

    def build(self, **factory_kwargs: Any) -> Any:
        """Compile and return the configured graph."""

        return self.factory(**factory_kwargs)


def _build_registry() -> dict[str, GraphDefinition]:
    from app.agents.graphs import (
        create_agent_graph,
        create_business_ops_graph,
        create_knowledge_qa_graph,
    )

    return {
        "agent": GraphDefinition(
            graph_id="agent",
            factory=create_agent_graph,
            node_ids=(
                "decide",
                "clarify",
                "invoke",
                "respond",
            ),
        ),
        "knowledge_qa": GraphDefinition(
            graph_id="knowledge_qa",
            factory=create_knowledge_qa_graph,
            node_ids=(
                "analyze_question",
                "plan_retrieval",
                "retrieve_knowledge",
                "compose_answer",
            ),
        ),
        "business_ops": GraphDefinition(
            graph_id="business_ops",
            factory=create_business_ops_graph,
            node_ids=(
                "analyze_request",
                "match_operation",
                "execute_operation",
                "compose_result",
            ),
        ),
    }


def get_graph_definition(graph_id: str) -> GraphDefinition:
    """Return graph metadata for the given graph id."""

    registry = _build_registry()
    try:
        return registry[graph_id]
    except KeyError as exc:
        raise KeyError(f"Unknown graph id: {graph_id}") from exc


def build_graph(graph_id: str) -> Any:
    """Compile and return the requested graph."""

    return get_graph_definition(graph_id).build()
