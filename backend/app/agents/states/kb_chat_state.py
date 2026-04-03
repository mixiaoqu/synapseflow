"""State model for end-user knowledge-base chat."""

from typing import Any, Dict, List, Optional

from app.agents.runtime.context import BaseAgentContext


class KbChatState(BaseAgentContext, total=False):
    """End-user workflow state for single-round knowledge-base chat."""

    query: str
    knowledge_base_id: Optional[int]
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
    kb_retrieval_status: Optional[str]
