"""Centralized graph registry for SynapseFlow workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class GraphDefinition:
    """Metadata for a compiled graph factory."""

    graph_id: str
    factory: Callable[[], Any]
    node_ids: tuple[str, ...]

    def build(self) -> Any:
        """Compile and return the configured graph."""

        return self.factory()


def _build_registry() -> dict[str, GraphDefinition]:
    from app.agents.graphs import create_kb_chat_graph

    return {
        "kb_chat": GraphDefinition(
            graph_id="kb_chat",
            factory=create_kb_chat_graph,
            node_ids=("plan_query", "retrieve", "answer"),
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
