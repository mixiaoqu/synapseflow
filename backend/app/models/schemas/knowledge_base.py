"""Knowledge-base related schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    """Create knowledge base request."""

    name: str = Field(..., min_length=1, max_length=100, description="Knowledge base name")
    team_id: int = Field(default=1, description="Owning team id")
    description: str | None = Field(default=None, description="Knowledge base description")


class KnowledgeBaseUpdate(BaseModel):
    """Update knowledge base request."""

    name: str = Field(..., min_length=1, max_length=100, description="Knowledge base name")
    description: str | None = Field(default=None, description="Knowledge base description")


class KnowledgeBaseResponse(BaseModel):
    """Knowledge base response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    team_id: int
    description: str | None = None
    created_at: datetime
    updated_at: datetime

class KnowledgeBaseWithCount(KnowledgeBaseResponse):
    """Knowledge base response with document count."""

    document_count: int = 0
