"""Knowledge-base chat related schemas."""

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
