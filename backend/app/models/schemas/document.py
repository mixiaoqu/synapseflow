"""Document-related schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    """Create a document from text content."""

    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    document_type: str | None = Field(None, description="文档类型，如 txt/md/pdf/docx")
    knowledge_base_id: int | None = Field(None, description="所属知识库 ID")


class DocumentResponse(BaseModel):
    """Document detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    document_type: str | None = None
    size: int = 0
    version: int = 1
    knowledge_base_id: int | None = Field(None, description="所属知识库 ID")
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

    content: str = Field(..., description="更新后的文档内容")


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
