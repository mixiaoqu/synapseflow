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
    from app.agents.graphs import (
        create_doc_to_prototype_graph,
        create_kb_chat_graph,
        create_kb_curation_graph,
        create_suggest_revision_graph,
        get_doc_to_prototype_pipeline_node_ids,
    )

    prototype_node_ids = get_doc_to_prototype_pipeline_node_ids()

    return {
        "kb_chat": GraphDefinition(
            graph_id="kb_chat",
            factory=create_kb_chat_graph,
            node_ids=("retrieve", "answer"),
        ),
        "kb_curation": GraphDefinition(
            graph_id="kb_curation",
            factory=create_kb_curation_graph,
            node_ids=("query_optimizer", "retrieve", "answer", "evaluate"),
        ),
        "suggest_revision": GraphDefinition(
            graph_id="suggest_revision",
            factory=create_suggest_revision_graph,
            node_ids=("parse_suggestions", "analyze_document", "locate_edits", "revise"),
        ),
        "doc_to_prototype": GraphDefinition(
            graph_id="doc_to_prototype",
            factory=create_doc_to_prototype_graph,
            node_ids=prototype_node_ids,
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
