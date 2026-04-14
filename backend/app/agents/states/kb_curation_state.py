"""State model for admin-facing knowledge-base curation QA."""

from typing import Any, Dict, List, Optional

from app.agents.runtime.context import BaseAgentContext


class KbCurationState(BaseAgentContext, total=False):
    """Admin workflow state for iterative knowledge-base curation."""

    query: str
    optimized_query: str
    knowledge_base_id: Optional[int]
    category_id: Optional[int]
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
