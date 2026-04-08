"""Knowledge-base chat related schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KbChatRequest(BaseModel):
    """Knowledge-base chat request."""

    query: str = Field(..., description="User question")
    knowledge_base_id: Optional[int] = Field(None, description="Limit retrieval to one KB")
    category_id: Optional[int] = Field(None, description="Limit retrieval to one category")
    session_id: Optional[str] = Field(None, description="Optional session id")


class KbChatResponse(BaseModel):
    """Knowledge-base chat response."""

    answer: str = Field(..., description="Answer content")
    retrieved_docs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved document chunks",
    )
    session_id: Optional[str] = None


class KbChatSessionMessage(BaseModel):
    """One persisted message in a KB chat session."""

    role: str = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Creation timestamp")


class KbChatSessionSummary(BaseModel):
    """Summary item for a user's persisted KB chat session."""

    session_id: str = Field(..., description="Stable session identifier")
    title: str = Field(..., description="Display title derived from the conversation")
    preview: Optional[str] = Field(None, description="Short preview of the latest message")
    knowledge_base_id: Optional[int] = Field(None, description="Selected knowledge base id")
    knowledge_base_name: Optional[str] = Field(None, description="Selected knowledge base name")
    category_id: Optional[int] = Field(None, description="Selected category id")
    category_name: Optional[str] = Field(None, description="Selected category name")
    message_count: int = Field(..., description="Persisted message count")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class KbChatSessionDetail(KbChatSessionSummary):
    """Full detail for a persisted KB chat session."""

    messages: List[KbChatSessionMessage] = Field(
        default_factory=list,
        description="Persisted chat messages in chronological order",
    )
