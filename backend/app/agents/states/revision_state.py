"""递归修订状态定义"""
from typing import TypedDict, List, Dict, Any


class RecursiveRevisionState(TypedDict):
    """递归修订状态"""
    original_doc: str
    current_doc: str
    document_structure: Dict[str, Any]
    missing_items: List[Dict[str, Any]]
    revision_history: List[Dict[str, Any]]
    current_revision: str
    validation_result: Dict[str, Any]
    iteration: int
    max_iterations: int
    is_complete: bool
    confidence: float
