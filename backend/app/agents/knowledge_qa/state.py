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
    question_type: Optional[str]
    retrieval_strategy: Optional[str]
    retrieval_complexity: Optional[str]
    needs_path: bool
    needs_relation: bool
    needs_summary: bool
    retrieval_execution_plan: Dict[str, Any]
    semantic_queries: List[str]
    lexical_terms: List[str]
    candidate_entities: List[str]
    relation_pairs: List[Dict[str, Any]]
    relation_queries: List[Dict[str, Any]]
    target_attributes: List[str]
    entity_constraints: Dict[str, Any]
    plan_trace: Dict[str, Any]
    query_plan_trace: Dict[str, Any]
    answer_status: str
