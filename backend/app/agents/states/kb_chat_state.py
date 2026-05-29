"""State model for the knowledge-base chat workflow."""

from typing import Any, Dict, List, Optional

from app.agents.runtime.context import BaseAgentContext


class KbChatState(BaseAgentContext, total=False):
    """Workflow state for kb_chat."""

    workflow_id: str
    session_id: Optional[str]
    query: str
    assistant_id: Optional[int]
    assistant_name: Optional[str]
    assistant_welcome_message: Optional[str]
    assistant_placeholder_text: Optional[str]
    assistant_llm_model_key: Optional[str]
    assistant_persona_prompt: Optional[str]
    assistant_rule_template: Optional[str]
    assistant_suggested_prompts: List[str]
    page_context: Dict[str, Any]
    page_config: Dict[str, Any]
    knowledge_base_id: Optional[int]
    knowledge_base_ids: List[int]
    category_id: Optional[int]
    chat_history: List[Dict[str, Any]]
    memory_summary: Optional[str]
    allowed_document_statuses: List[str]
    retrieval_version_mode: str

    question_type: Optional[str]
    retrieval_strategy: Optional[str]
    retrieval_complexity: Optional[str]
    retrieval_required: bool
    needs_clarification: bool
    route_reason: str
    route_trace: Dict[str, Any]
    semantic_queries: List[str]
    lexical_terms: List[str]
    candidate_entities: List[str]
    relation_pairs: List[Dict[str, Any]]
    relation_queries: List[Dict[str, Any]]
    target_attributes: List[str]
    entity_constraints: Dict[str, Any]
    plan_trace: Dict[str, Any]
    rewrite_trace: Dict[str, Any]
    retrieval_trace: Dict[str, Any]
    retrieval_evaluation: Dict[str, Any]
    evaluate_trace: Dict[str, Any]
    retrieved_docs: List[Dict[str, Any]]
    graph_primary_docs: List[Dict[str, Any]]
    graph_supporting_docs: List[Dict[str, Any]]
    primary_evidence_docs: List[Dict[str, Any]]
    supporting_evidence_docs: List[Dict[str, Any]]
    metadata_evidence_docs: List[Dict[str, Any]]
    primary_context: str
    supporting_context: str
    metadata_context: str
    context: str
    answer: str
    answer_status: str
    answer_trace: Dict[str, Any]

    retrieval_execution_plan: Dict[str, Any]
    graph_enabled: bool
    graph_intent: Optional[str]
    graph_mode: Optional[str]
    graph_requires_grounding: bool
    graph_max_hops: int
    graph_budget: int
    fusion_policy: Optional[str]
    graph_boost: Optional[str]
    reranked_primary_evidence_docs: List[Dict[str, Any]]
