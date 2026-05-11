"""State model for end-user knowledge-base chat."""

from typing import Any, Dict, List, Optional

from app.agents.runtime.context import BaseAgentContext


class KbChatState(BaseAgentContext, total=False):
    """End-user workflow state for single-round knowledge-base chat."""

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
    knowledge_base_branch_ids: List[int]
    category_id: Optional[int]
    chat_history: List[Dict[str, Any]]
    memory_summary: Optional[str]
    retrieval_plan: Dict[str, Any]
    retrieval_queries: List[str]
    rewrite_meta: Dict[str, Any]
    retrieval_funnel: Dict[str, Any]
    allowed_document_statuses: List[str]
    retrieval_version_mode: str
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
    kb_retrieval_status: Optional[str]
