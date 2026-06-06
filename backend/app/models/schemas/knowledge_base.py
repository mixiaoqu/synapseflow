"""Knowledge-base related schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KnowledgeBaseStatus = Literal["available", "indexing", "error", "empty"]
DocumentIndexStatus = Literal["queued", "processing", "indexed", "failed"]
KnowledgeBaseBulkAction = Literal["enable", "disable", "delete", "reindex"]


class KnowledgeBaseCreate(BaseModel):
    """Create knowledge base request."""

    name: str = Field(..., min_length=1, max_length=100, description="Knowledge base name")
    team_id: int = Field(default=1, description="Owning team id")
    description: str | None = Field(default=None, description="Knowledge base description")


class KnowledgeBaseUpdate(BaseModel):
    """Update knowledge-base request."""

    name: str = Field(..., min_length=1, max_length=100, description="Knowledge base name")
    description: str | None = Field(default=None, description="Knowledge base description")


class KnowledgeBaseResponse(BaseModel):
    """Knowledge-base response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    team_id: int
    description: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseRecentDocument(BaseModel):
    """Recent document summary used in knowledge-base cards."""

    id: int
    title: str
    document_type: str | None = None
    size: int = 0
    indexed: bool = False
    index_status: DocumentIndexStatus = "queued"
    index_error: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListItem(KnowledgeBaseResponse):
    """Knowledge-base list item with document counts and status."""

    document_count: int = 0
    indexed_document_count: int = 0
    queued_document_count: int = 0
    processing_document_count: int = 0
    failed_document_count: int = 0
    unindexed_document_count: int = 0
    draft_document_count: int = 0
    submittable_document_count: int = 0
    pending_review_document_count: int = 0
    published_document_count: int = 0
    archived_document_count: int = 0
    last_document_updated_at: datetime | None = None
    last_uploaded_at: datetime | None = None
    status: KnowledgeBaseStatus = "empty"


class KnowledgeBaseWithCount(KnowledgeBaseListItem):
    """Knowledge-base response with document counts and recent documents."""

    recent_documents: list[KnowledgeBaseRecentDocument] = Field(default_factory=list)


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class KnowledgeBaseToggleActive(BaseModel):
    """Toggle knowledge-base active state."""

    is_active: bool


class KnowledgeBaseBulkActionRequest(BaseModel):
    """Batch knowledge-base action request."""

    knowledge_base_ids: list[int] = Field(
        ...,
        min_length=1,
        description="Knowledge base ids",
    )
    action: KnowledgeBaseBulkAction = Field(..., description="Batch action")


class KnowledgeBaseBulkActionFailure(BaseModel):
    """Single failed item in a batch knowledge-base action."""

    id: int
    message: str


class KnowledgeBaseBulkActionResponse(BaseModel):
    """Batch knowledge-base action result."""

    action: KnowledgeBaseBulkAction
    total: int = 0
    affected: int = 0
    failed: list[KnowledgeBaseBulkActionFailure] = Field(default_factory=list)
