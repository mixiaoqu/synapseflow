"""State model for end-user knowledge-base chat."""

from typing import Any, Dict, List, Optional

from app.agents.runtime.context import BaseAgentContext


class KbChatState(BaseAgentContext, total=False):
    """End-user workflow state for single-round knowledge-base chat."""

    session_id: Optional[str]
    query: str
    knowledge_base_id: Optional[int]
    category_id: Optional[int]
    chat_history: List[Dict[str, Any]]
    memory_summary: Optional[str]
    retrieval_queries: List[str]
    retrieval_funnel: Dict[str, Any]
    allowed_document_statuses: List[str]
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
    kb_retrieval_status: Optional[str]
