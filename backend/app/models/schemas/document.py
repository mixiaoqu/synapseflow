"""Document-related schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.utils.time import serialize_utc_datetime

DocumentIndexStatus = Literal["queued", "processing", "indexed", "failed"]
DocumentLifecycleStatus = Literal[
    "draft",
    "pending_review",
    "approved",
    "published",
    "archived",
]
IndexJobStatus = Literal["queued", "processing", "completed", "partial_failed", "failed"]
UTC_MODEL_CONFIG = ConfigDict(json_encoders={datetime: serialize_utc_datetime})


class DocumentCreate(BaseModel):
    """Create a document from text content."""

    model_config = UTC_MODEL_CONFIG

    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    document_type: str | None = Field(None, description="Document type such as txt/md/pdf/docx")
    knowledge_base_id: int | None = Field(None, description="Owning knowledge base id")
    category_id: int | None = Field(None, description="Owning category id")
    source_path: str | None = Field(None, description="Original relative source path")


class DocumentResponse(BaseModel):
    """Document detail response."""

    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: serialize_utc_datetime})

    id: int
    title: str
    content: str
    document_type: str | None = None
    size: int = 0
    version: int = 1
    is_current: bool = True
    is_latest: bool = True
    is_live: bool = False
    knowledge_base_id: int | None = Field(None, description="Owning knowledge base id")
    category_id: int | None = Field(None, description="Owning category id")
    category_name: str | None = Field(None, description="Owning category name")
    source_path: str | None = Field(None, description="Original relative source path")
    status: DocumentLifecycleStatus = "draft"
    published_at: datetime | None = None
    published_by: int | None = None
    reviewed_at: datetime | None = None
    reviewed_by: int | None = None
    index_status: DocumentIndexStatus = "queued"
    index_error: str | None = None
    indexed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListItem(BaseModel):
    """Document list item."""

    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: serialize_utc_datetime})

    id: int
    title: str
    document_type: str | None = None
    size: int = 0
    version: int = 1
    is_current: bool = True
    is_latest: bool = True
    is_live: bool = False
    indexed: bool = False
    index_status: DocumentIndexStatus = "queued"
    index_error: str | None = None
    indexed_at: datetime | None = None
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    source_path: str | None = None
    status: DocumentLifecycleStatus = "draft"
    published_at: datetime | None = None
    published_by: int | None = None
    reviewed_at: datetime | None = None
    reviewed_by: int | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated document list response."""

    model_config = UTC_MODEL_CONFIG

    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int


class DocumentContentUpdate(BaseModel):
    """Update document content request."""

    model_config = UTC_MODEL_CONFIG

    content: str = Field(..., description="Updated document content")


class DocumentStatusUpdateResponse(DocumentResponse):
    """Document response used by publish/review transitions."""


class DocumentStatusActionRequest(BaseModel):
    """Optional note placeholder for status transitions."""

    model_config = UTC_MODEL_CONFIG

    note: str | None = Field(default=None, description="Optional admin note")


class DocumentVersionItem(BaseModel):
    """Document version item."""

    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: serialize_utc_datetime})

    id: int
    title: str
    version: int
    is_latest: bool
    is_current: bool
    is_live: bool
    created_at: datetime


class DocumentVersionsResponse(BaseModel):
    """Document version list response."""

    model_config = UTC_MODEL_CONFIG

    items: list[DocumentVersionItem]


class ActiveIndexingJob(BaseModel):
    """Compact progress summary for one active indexing job."""

    model_config = UTC_MODEL_CONFIG

    job_id: int
    title: str
    job_type: str
    job_status: IndexJobStatus
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    queued: int
    processing: int
    indexed: int
    failed: int
    total: int
    created_at: datetime
    updated_at: datetime | None = None
    progress_percent: int


class FailedIndexingItem(BaseModel):
    """Recent failed indexing document entry for the task panel."""

    model_config = UTC_MODEL_CONFIG

    job_id: int
    document_id: int
    title: str
    job_title: str
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    index_error: str | None = None
    updated_at: datetime


class IndexingPanelSummaryResponse(BaseModel):
    """Aggregated task-panel payload for document indexing."""

    model_config = UTC_MODEL_CONFIG

    queued: int
    processing: int
    indexed: int
    failed: int
    total: int
    has_active: bool
    active_job_count: int
    active_jobs: list[ActiveIndexingJob]
    recent_failed: list[FailedIndexingItem]
