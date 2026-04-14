"""Workflow display metadata used by streaming services."""

from __future__ import annotations

from typing import Any

WORKFLOW_NODE_META: dict[str, dict[str, dict[str, Any]]] = {
    "kb_chat": {
        "retrieve": {"label": "Retrieve"},
        "answer": {"label": "Answer"},
    },
    "kb_curation": {
        "query_optimizer": {"label": "Query Optimizer"},
        "retrieve": {"label": "Retrieve"},
        "answer": {"label": "Answer"},
        "evaluate": {"label": "Evaluate"},
    },
    "doc_to_prototype": {
        "prepare_requirement_chunks": {
            "label": "Prepare Chunks",
            "model": "local-splitter",
        },
        "chunk_understanding": {
            "label": "Chunk Understanding",
            "model": "Qwen3.5-Plus-analysis",
        },
        "structure_extraction": {
            "label": "Structure Extraction",
            "model": "Qwen3.5-Plus-analysis",
        },
        "normalize_spec": {
            "label": "Normalize Spec",
            "model": "Qwen3.5-Plus-analysis",
        },
        "product_design": {
            "label": "Product Design",
            "model": "Qwen3.5-Plus-planning",
        },
        "interaction_design": {
            "label": "Interaction Design",
            "model": "Qwen3.5-Plus-planning",
        },
        "generate_prototype_from_spec": {
            "label": "Generate Prototype",
            "model": "Qwen3.5-Plus-generation",
        },
    },
}


def get_node_label(workflow_id: str, node_id: str) -> str:
    """Return the display label for a workflow node."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("label", node_id)


def get_node_model(workflow_id: str, node_id: str) -> str | None:
    """Return the display model name for a workflow node, if configured."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("model")
