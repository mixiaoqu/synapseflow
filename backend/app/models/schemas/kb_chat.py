"""Knowledge-base chat related schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KbChatRequest(BaseModel):
    """Knowledge-base chat request."""

    query: str = Field(..., description="User question")
    team_id: Optional[int] = Field(None, description="Limit retrieval to one team")
    knowledge_base_id: Optional[int] = Field(None, description="Limit retrieval to one KB")
    category_id: Optional[int] = Field(None, description="Limit retrieval to one category")
    assistant_id: Optional[int] = Field(None, description="Assistant profile id")
    session_id: Optional[str] = Field(None, description="Optional session id")


class KbChatResponse(BaseModel):
    """Knowledge-base chat response."""

    answer: str = Field(..., description="Answer content")
    answer_text: str = Field(..., description="Answer content for end-user rendering")
    answer_status: str = Field("answered", description="Answer confidence/result state")
    confidence_level: str | None = Field(None, description="Optional confidence band")
    backend_citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved citations retained for admin QA",
    )
    retrieved_docs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved document chunks",
    )
    assistant_id: Optional[int] = None
    assistant_name: Optional[str] = None
    session_id: Optional[str] = None
    log_id: Optional[int] = None


class KbChatSessionMessage(BaseModel):
    """One persisted message in a KB chat session."""

    role: str = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    retrieved_docs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved document chunks for one assistant message",
    )
    answer_status: Optional[str] = Field(None, description="Persisted answer state")
    log_id: Optional[int] = Field(None, description="Persisted KB chat log id")
    created_at: datetime = Field(..., description="Creation timestamp")


class KbChatSessionSummary(BaseModel):
    """Summary item for a user's persisted KB chat session."""

    session_id: str = Field(..., description="Stable session identifier")
    title: str = Field(..., description="Display title derived from the conversation")
    preview: Optional[str] = Field(None, description="Short preview of the latest message")
    team_id: Optional[int] = Field(None, description="Selected team id")
    knowledge_base_id: Optional[int] = Field(None, description="Selected knowledge base id")
    knowledge_base_name: Optional[str] = Field(None, description="Selected knowledge base name")
    assistant_id: Optional[int] = Field(None, description="Selected assistant id")
    assistant_name: Optional[str] = Field(None, description="Selected assistant name")
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


class KbChatPreviewRequest(KbChatRequest):
    """Admin-only KB preview request that can read unpublished content."""

    include_unpublished: bool = Field(
        default=True,
        description="Whether to include draft/indexed content in retrieval",
    )


class KbChatFeedbackRequest(BaseModel):
    """User feedback for one KB chat log entry."""

    feedback_value: str = Field(..., min_length=1, max_length=20)
    feedback_note: str | None = Field(default=None, max_length=1000)


class KbChatReviewRequest(BaseModel):
    """Admin review label and note for one KB chat log entry."""

    review_label: str | None = Field(default=None, max_length=40)
    review_note: str | None = Field(default=None, max_length=1000)


class KbChatLogItem(BaseModel):
    """Admin-facing KB chat log item."""

    id: int
    user_id: int
    session_id: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    assistant_id: int | None = None
    assistant_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    query: str
    answer_text: str
    answer_status: str
    retrieval_status: str | None = None
    retrieved_count: int = 0
    latency_ms: int | None = None
    feedback_value: str | None = None
    feedback_note: str | None = None
    suggested_review_label: str | None = None
    review_label: str | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by_user_id: int | None = None
    created_at: datetime


class KbChatDiagnosticDoc(BaseModel):
    """One retrieved chunk retained for QA diagnostics."""

    rank: int = 0
    content: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KbChatDiagnosticMessage(BaseModel):
    """One surrounding message for diagnostic context."""

    role: str
    content: str
    created_at: datetime
    is_current_turn: bool = False


class KbChatRetrievalQueryStat(BaseModel):
    """One rewritten retrieval query and its recall count."""

    query: str
    chunk_count: int = 0


class KbChatRetrievalFunnelStage(BaseModel):
    """One stage in the retrieval funnel."""

    key: str
    label: str
    chunk_count: int = 0
    note: str | None = None


class KbChatRetrievalFunnel(BaseModel):
    """Structured retrieval funnel retained for diagnostics."""

    mode: str | None = None
    query_count: int = 0
    rewritten_queries: List[KbChatRetrievalQueryStat] = Field(default_factory=list)
    stages: List[KbChatRetrievalFunnelStage] = Field(default_factory=list)


class KbChatLogDetail(KbChatLogItem):
    """Admin-facing detailed diagnostic view for one KB chat log."""

    team_id: int | None = None
    team_name: str | None = None
    assistant_id: int | None = None
    assistant_name: str | None = None
    category_name: str | None = None
    retrieval_status_reason: str | None = None
    retrieval_queries: List[str] = Field(default_factory=list)
    retrieval_funnel: KbChatRetrievalFunnel | None = None
    answer_context: str | None = None
    retrieved_docs: List[KbChatDiagnosticDoc] = Field(default_factory=list)
    conversation_context: List[KbChatDiagnosticMessage] = Field(default_factory=list)


class KbChatLogListResponse(BaseModel):
    """Admin-facing KB chat log list response."""

    items: List[KbChatLogItem] = Field(default_factory=list)
    total: int = 0
