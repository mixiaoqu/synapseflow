"""State model for the document-to-prototype workflow."""

from __future__ import annotations

from typing import Any, Dict, List

from app.agents.runtime.context import BaseAgentContext, merge_agent_state


class DocToPrototypeState(BaseAgentContext, total=False):
    """Workflow state used by the prototype generation graph."""

    requirements_doc: str
    extracted_requirements: Dict[str, Any]
    ui_components: List[Dict[str, Any]]
    design_system: Dict[str, Any]
    generated_html: str
    validation_errors: List[str]
    preview_url: str
    is_valid: bool
    metadata: Dict[str, Any]
    requirements_chunks: List[Dict[str, Any]]
    chunk_summaries: List[Dict[str, Any]]
    structured_spec: Dict[str, Any]
    normalized_spec: Dict[str, Any]
    product_spec: Dict[str, Any]
    interaction_spec: Dict[str, Any]
    site_map: List[Dict[str, Any]]
    page_html: Dict[str, str]
    generation_mode: str
    prototype_revision_used: int
    prototype_revision_target: str


def prototype_state(requirements_doc: str) -> DocToPrototypeState:
    """Build the default state for prototype generation."""

    return merge_agent_state(
        {
            "messages": [],
            "user_id": None,
            "team_id": None,
            "knowledge_base_id": None,
            "request_id": None,
            "run_id": None,
            "metadata": {},
        },
        {
            "requirements_doc": requirements_doc,
            "extracted_requirements": {},
            "ui_components": [],
            "design_system": {},
            "generated_html": "",
            "validation_errors": [],
            "preview_url": "",
            "is_valid": False,
            "requirements_chunks": [],
            "chunk_summaries": [],
            "structured_spec": {},
            "normalized_spec": {},
            "product_spec": {},
            "interaction_spec": {},
            "site_map": [],
            "page_html": {},
            "generation_mode": "single",
            "prototype_revision_used": 0,
            "prototype_revision_target": "",
        },
    )
