"""State model for the revision workflow."""

from typing import Any, Dict, List, Optional

from app.agents.runtime.context import BaseAgentContext


class UserDrivenRevisionState(BaseAgentContext, total=False):
    """Workflow state used by user-driven revision."""

    original_doc: str
    current_doc: str
    user_suggestions: str
    parsed_tasks: List[Dict[str, Any]]
    doc_structure: List[Dict[str, Any]]
    chunks_meta: List[Any]
    chunks_positions: List[Any]
    affected_chunk_indices: List[int]
    section_hints: Dict[int, str]
    revised_document: str
    doc_id: Optional[int]
