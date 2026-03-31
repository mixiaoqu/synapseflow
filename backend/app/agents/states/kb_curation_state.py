"""State model for admin-facing knowledge-base curation QA."""

from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph.message import add_messages


class KbCurationState(TypedDict, total=False):
    """Admin workflow state for iterative knowledge-base curation."""

    messages: Annotated[List, add_messages]
    query: str
    optimized_query: str
    collection_id: Optional[int]
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
    confidence_score: float
    iteration: int
    max_iterations: int
    should_continue: bool
    iteration_history: List[Dict[str, Any]]
    last_evaluation_feedback: Optional[Dict[str, Any]]
    document_issues: List[Dict[str, Any]]
