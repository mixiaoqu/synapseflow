"""State model for end-user knowledge-base chat."""

from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph.message import add_messages


class KbChatState(TypedDict, total=False):
    """End-user workflow state for single-round knowledge-base chat."""

    messages: Annotated[List, add_messages]
    query: str
    collection_id: Optional[int]
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
    kb_retrieval_status: Optional[str]
