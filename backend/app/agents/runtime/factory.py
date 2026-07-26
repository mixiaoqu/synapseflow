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
    expose_in_langgraph: bool = False

    def build(self, **factory_kwargs: Any) -> Any:
        """Compile and return the configured graph."""

        return self.factory(**factory_kwargs)


def _build_registry() -> dict[str, GraphDefinition]:
    from app.agents.business_ops.graph import create_business_ops_graph
    from app.agents.knowledge_qa.graph import create_knowledge_qa_graph
    from app.agents.main.graph import create_agent_graph

    return {
        "agent": GraphDefinition(
            graph_id="agent",
            factory=create_agent_graph,
            node_ids=(
                "route",
                "plan",
                "execute",
                "aggregate",
                "respond",
            ),
            expose_in_langgraph=True,
        ),
        "knowledge_qa": GraphDefinition(
            graph_id="knowledge_qa",
            factory=create_knowledge_qa_graph,
            node_ids=(
                "plan_query",
                "plan_retrieval",
                "retrieve_knowledge",
                "compose_result",
            ),
            expose_in_langgraph=True,
        ),
        "business_ops": GraphDefinition(
            graph_id="business_ops",
            factory=create_business_ops_graph,
            node_ids=(
                "analyze_request",
                "match_operation",
                "execute_operation",
                "replan_operation_params",
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
