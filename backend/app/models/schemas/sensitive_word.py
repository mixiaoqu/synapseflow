"""Sensitive-word management schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SensitiveWordSettingsUpdate(BaseModel):
    """Update one scoped sensitive-word settings row."""

    enabled: bool = Field(default=True, description="Whether sensitive-word blocking is enabled")
    block_query: bool = Field(default=True, description="Whether to block ask queries")
    block_document_publish: bool = Field(
        default=False,
        description="Whether to block document publish when sensitive content is detected",
    )


class SensitiveWordSettingsResponse(BaseModel):
    """Scoped sensitive-word settings response."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    team_id: int | None = None
    enabled: bool = True
    block_query: bool = True
    block_document_publish: bool = False
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SensitiveWordCreate(BaseModel):
    """Create one sensitive-word rule."""

    team_id: int | None = Field(default=None, description="Null means the global scope")
    word: str = Field(..., min_length=1, max_length=255, description="Raw sensitive word")
    category: str | None = Field(default=None, max_length=50, description="Optional category")
    enabled: bool = Field(default=True, description="Whether this rule is enabled")
    remark: str | None = Field(default=None, max_length=1000, description="Optional note")


class SensitiveWordUpdate(BaseModel):
    """Update one sensitive-word rule."""

    word: str = Field(..., min_length=1, max_length=255, description="Raw sensitive word")
    category: str | None = Field(default=None, max_length=50, description="Optional category")
    enabled: bool = Field(default=True, description="Whether this rule is enabled")
    remark: str | None = Field(default=None, max_length=1000, description="Optional note")


class SensitiveWordResponse(BaseModel):
    """Sensitive-word rule response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int | None = None
    word: str
    normalized_word: str
    category: str | None = None
    match_mode: str
    enabled: bool
    remark: str | None = None
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class SensitiveWordListResponse(BaseModel):
    """Paginated sensitive-word list response."""

    items: list[SensitiveWordResponse] = Field(default_factory=list)
    total: int = 0
    enabled_count: int = 0
    disabled_count: int = 0
    page: int = 1
    page_size: int = 20


class SensitiveWordImportRequest(BaseModel):
    """Bulk-import sensitive words from a textarea-like payload."""

    team_id: int | None = Field(default=None, description="Null means the global scope")
    words_text: str = Field(..., min_length=1, description="One word per line")
    category: str | None = Field(default=None, max_length=50, description="Optional category")
    enabled: bool = Field(default=True, description="Whether imported rows are enabled")


class SensitiveWordImportResponse(BaseModel):
    """Bulk-import result summary."""

    created_count: int = 0
    skipped_count: int = 0
    items: list[SensitiveWordResponse] = Field(default_factory=list)


class SensitiveWordCheckRequest(BaseModel):
    """Preview whether a text would be blocked."""

    text: str = Field(..., min_length=1, description="Text to be checked")
    team_id: int | None = Field(default=None, description="Optional team scope")
    scene: str = Field(default="query", description="Query or document_publish")


class SensitiveWordCheckResponse(BaseModel):
    """Sensitive-word check response."""

    blocked: bool = False
    matched_words: list[str] = Field(default_factory=list)
    scene: str = "query"
    reason: str | None = None
