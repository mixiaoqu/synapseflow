"""State contract for the knowledge-base QA workflow."""

from typing import Any, Dict, List, Optional

from app.agents.runtime.context import BaseAgentContext


class KnowledgeQaState(BaseAgentContext, total=False):
    """Workflow state for knowledge_qa."""

    workflow_id: str
    session_id: Optional[str]
    original_query: str
    query: str
    intent: Dict[str, Any]
    dependency_results: Dict[str, Dict[str, Any]]
    page_context: Dict[str, Any]
    allowed_document_statuses: List[str]

    retrieval_result: Dict[str, Any]
    sub_agent_result: Dict[str, Any]

    retrieval_analysis: Dict[str, Any]
    retrieval_strategy: Optional[str]
    retrieval_profile: Optional[str]
    retrieval_execution_plan: Dict[str, Any]
    normalized_query: str
    current_query_plan: Dict[str, Any]
    query_plan_attempt: int
    replan_exhausted: bool
    retrieval_feedback: Dict[str, Any]
    retrieval_attempts: List[Dict[str, Any]]
    accumulated_evidence_items: List[Dict[str, Any]]
    accumulated_candidate_docs: List[Dict[str, Any]]
    should_replan: bool
    semantic_queries: List[str]
    lexical_terms: List[str]
    plan_trace: Dict[str, Any]
    query_plan_trace: Dict[str, Any]
    answer_status: str
