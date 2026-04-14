"""Document-category related schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCategoryCreate(BaseModel):
    """Create a category inside a knowledge base."""

    knowledge_base_id: int = Field(..., description="Owning knowledge base id")
    name: str = Field(..., min_length=1, max_length=100, description="Category name")


class DocumentCategoryUpdate(BaseModel):
    """Rename a document category."""

    name: str = Field(..., min_length=1, max_length=100, description="Category name")


class DocumentCategoryResponse(BaseModel):
    """Document-category response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    name: str
    document_count: int = 0
    created_at: datetime
    updated_at: datetime
