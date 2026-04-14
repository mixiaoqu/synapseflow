"""Knowledge-base curation related schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QARequest(BaseModel):
    """Knowledge-base curation request."""

    query: str = Field(..., description="User question")
    max_iterations: int = Field(default=3, ge=1, le=5, description="Maximum iteration count")
    session_id: Optional[str] = Field(None, description="Session id")
    knowledge_base_id: Optional[int] = Field(None, description="Limit retrieval to one KB")
    category_id: Optional[int] = Field(None, description="Limit retrieval to one category")


class IterationRecord(BaseModel):
    """Single iteration record."""

    round: int
    question: str
    original_question: str
    answer: str
    score: float
    passed: bool
    reason: Optional[str] = None
    suggestion: Optional[str] = None


class QAResponse(BaseModel):
    """Knowledge-base curation response."""

    answer: str = Field(..., description="Answer content")
    confidence_score: float = Field(..., description="Confidence score")
    iteration: int = Field(..., description="Actual iteration count")
    retrieved_docs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved document chunks",
    )
    iteration_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Iteration history",
    )
    document_issues: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Document issues discovered during curation",
    )
    session_id: Optional[str] = None
