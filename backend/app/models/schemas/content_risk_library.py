"""Content-risk rule library schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContentRiskLibraryResponse(BaseModel):
    """Rule library summary for admin list pages."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    enabled: bool = True
    rule_count: int = 0
    reference_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContentRiskLibraryCreate(BaseModel):
    """Create one content-risk rule library."""

    name: str = Field(..., min_length=1, max_length=100, description="Rule library name")
    description: str | None = Field(default=None, max_length=1000, description="Optional description")
    enabled: bool = Field(default=True, description="Whether this library is enabled")


class ContentRiskLibraryUpdate(BaseModel):
    """Update one content-risk rule library."""

    name: str = Field(..., min_length=1, max_length=100, description="Rule library name")
    description: str | None = Field(default=None, max_length=1000, description="Optional description")
    enabled: bool = Field(default=True, description="Whether this library is enabled")


class ContentRiskLibraryListResponse(BaseModel):
    """Content-risk library list response."""

    items: list[ContentRiskLibraryResponse] = Field(default_factory=list)


ContentRiskRuleType = Literal["keyword", "regex"]
ContentRiskMatchMode = Literal["contains", "exact", "regex"]
ContentRiskLevel = Literal["low", "medium", "high"]
ContentRiskAction = Literal["block", "review", "log"]
ContentRiskScene = Literal["query", "answer"]
ContentRiskResolvedAction = Literal["pass", "block", "review", "log"]


class ContentRiskRuleResponse(BaseModel):
    """Concrete content-risk rule response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    library_id: int
    name: str
    description: str | None = None
    rule_type: ContentRiskRuleType
    match_mode: ContentRiskMatchMode
    pattern: str
    risk_category: str
    risk_level: ContentRiskLevel
    default_action: ContentRiskAction
    applies_to_query: bool = True
    applies_to_answer: bool = True
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContentRiskRuleCreate(BaseModel):
    """Create one concrete content-risk rule."""

    name: str = Field(..., min_length=1, max_length=100, description="Rule name")
    description: str | None = Field(default=None, max_length=1000, description="Optional description")
    rule_type: ContentRiskRuleType = Field(default="keyword", description="Rule type")
    match_mode: ContentRiskMatchMode = Field(default="contains", description="Match mode")
    pattern: str = Field(..., min_length=1, max_length=5000, description="Keyword list or regex pattern")
    risk_category: str = Field(..., min_length=1, max_length=50, description="Risk category")
    risk_level: ContentRiskLevel = Field(default="medium", description="Risk level")
    default_action: ContentRiskAction = Field(default="block", description="Default suggested action")
    applies_to_query: bool = Field(default=True, description="Whether to check user queries")
    applies_to_answer: bool = Field(default=True, description="Whether to check assistant answers")
    enabled: bool = Field(default=True, description="Whether this rule is enabled")


class ContentRiskRuleUpdate(ContentRiskRuleCreate):
    """Update one concrete content-risk rule."""


class ContentRiskRuleListResponse(BaseModel):
    """Content-risk rule list response."""

    items: list[ContentRiskRuleResponse] = Field(default_factory=list)


class ContentRiskTestRequest(BaseModel):
    """Request for testing text against enabled global content-risk rules."""

    scene: ContentRiskScene = Field(..., description="Detection scene")
    text: str = Field(..., min_length=1, max_length=5000, description="Text to test")


class ContentRiskRuleHitResponse(BaseModel):
    """One content-risk rule hit."""

    rule_id: int
    library_id: int
    rule_name: str
    risk_category: str
    risk_level: ContentRiskLevel
    action: ContentRiskAction
    match_mode: ContentRiskMatchMode
    pattern: str
    matched_text: str


class ContentRiskTestResponse(BaseModel):
    """Aggregated detection response."""

    scene: ContentRiskScene
    action: ContentRiskResolvedAction
    blocked: bool = False
    risk_level: ContentRiskLevel | None = None
    elapsed_ms: int = 0
    hits: list[ContentRiskRuleHitResponse] = Field(default_factory=list)


class ContentRiskLogResponse(BaseModel):
    """One persisted content-risk detection log."""

    id: int
    chat_log_id: int | None = None
    user_id: int | None = None
    session_id: str | None = None
    product_id: int | None = None
    product_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    project_app_id: int | None = None
    project_app_name: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    external_user_id: str | None = None
    external_user_name: str | None = None
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    assistant_id: int | None = None
    assistant_name: str | None = None
    scene: ContentRiskScene
    action: ContentRiskResolvedAction
    blocked: bool
    risk_level: ContentRiskLevel | None = None
    matched_text: str | None = None
    checked_text: str
    hits: list[ContentRiskRuleHitResponse] = Field(default_factory=list)
    elapsed_ms: int
    created_at: datetime | None = None


class ContentRiskLogListResponse(BaseModel):
    """Content-risk log list response."""

    items: list[ContentRiskLogResponse] = Field(default_factory=list)
    total: int = 0
