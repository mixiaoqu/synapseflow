"""Document-related schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentIndexStatus = Literal["queued", "processing", "indexed", "failed"]


class DocumentCreate(BaseModel):
    """Create a document from text content."""

    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    document_type: str | None = Field(None, description="Document type such as txt/md/pdf/docx")
    knowledge_base_id: int | None = Field(None, description="Owning knowledge base id")


class DocumentResponse(BaseModel):
    """Document detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    document_type: str | None = None
    size: int = 0
    version: int = 1
    knowledge_base_id: int | None = Field(None, description="Owning knowledge base id")
    index_status: DocumentIndexStatus = "queued"
    index_error: str | None = None
    indexed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListItem(BaseModel):
    """Document list item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    document_type: str | None = None
    size: int = 0
    version: int = 1
    indexed: bool = False
    index_status: DocumentIndexStatus = "queued"
    index_error: str | None = None
    indexed_at: datetime | None = None
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated document list response."""

    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int


class DocumentContentUpdate(BaseModel):
    """Update document content request."""

    content: str = Field(..., description="Updated document content")


class DocumentVersionItem(BaseModel):
    """Document version item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    version: int
    is_latest: bool
    is_current: bool
    created_at: datetime


class DocumentVersionsResponse(BaseModel):
    """Document version list response."""

    items: list[DocumentVersionItem]
