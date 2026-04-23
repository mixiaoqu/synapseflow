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
    knowledge_base_id: Optional[int]
    category_id: Optional[int]
    chat_history: List[Dict[str, Any]]
    memory_summary: Optional[str]
    adaptive_policy: Dict[str, Any]
    retrieval_queries: List[str]
    retrieval_funnel: Dict[str, Any]
    allowed_document_statuses: List[str]
    retrieval_version_mode: str
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
    kb_retrieval_status: Optional[str]
