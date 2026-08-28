"""Assistant profile schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.utils.time import serialize_utc_datetime

UTC_MODEL_CONFIG = ConfigDict(json_encoders={datetime: serialize_utc_datetime})


class AssistantPromptConfigMixin(BaseModel):
    """Shared assistant prompt/display fields."""

    description: str | None = Field(default=None, description="Assistant description")
    welcome_message: str | None = Field(default=None, description="Greeting shown in the UI")
    placeholder_text: str | None = Field(default=None, description="Input placeholder text")
    llm_model_key: str | None = Field(default=None, max_length=80, description="Selected chat model asset key")
    persona_prompt: str | None = Field(default=None, description="Assistant persona instructions")
    rule_template: str | None = Field(default=None, description="Assistant-specific answer rules")
    suggested_prompts: list[str] = Field(
        default_factory=list,
        description="Suggested questions shown before the user starts chatting",
    )
    is_active: bool = Field(default=True, description="Whether the assistant is active")
    sort_order: int = Field(default=0, description="Display order")


class AssistantProfileCreate(AssistantPromptConfigMixin):
    """Create assistant profile request."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=120)
    current_team_id: int = Field(..., gt=0)


class AssistantProfileUpdate(AssistantPromptConfigMixin):
    """Update assistant profile request."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=120)
    current_team_id: int = Field(..., gt=0)


class AssistantPreviewRequest(AssistantPromptConfigMixin):
    """Preview assistant behavior without persisting the profile."""

    query: str = Field(..., min_length=1, description="Preview question")
    current_team_id: int = Field(..., gt=0)
    name: str | None = Field(default=None, max_length=100)
    include_unpublished: bool = Field(
        default=True,
        description="Whether preview can retrieve current working content before publish",
    )


class AssistantProfileSummary(BaseModel):
    """Assistant summary payload."""

    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: serialize_utc_datetime})

    id: int
    name: str
    slug: str
    team_id: int
    team_name: str | None = None
    created_by_user_id: int | None = None
    created_by_name: str | None = None
    description: str | None = None
    welcome_message: str | None = None
    placeholder_text: str | None = None
    llm_model_key: str | None = None
    suggested_prompts: list[str] = Field(default_factory=list)
    is_active: bool = True
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime


class AssistantProfileListResponse(BaseModel):
    model_config = UTC_MODEL_CONFIG

    items: list[AssistantProfileSummary] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class AssistantProfileResponse(AssistantProfileSummary):
    """Assistant detail payload including prompt configuration."""

    persona_prompt: str | None = None
    rule_template: str | None = None


class AssistantModelOption(BaseModel):
    """One selectable assistant model asset."""

    key: str
    name: str
    provider: str
    model: str


class AssistantModelOptionsResponse(BaseModel):
    """Available assistant model assets."""

    items: list[AssistantModelOption] = Field(default_factory=list)


class AssistantAvailabilityResponse(BaseModel):
    """Available assistants response."""

    model_config = UTC_MODEL_CONFIG

    items: list[AssistantProfileSummary] = Field(default_factory=list)


class AssistantDependencyUsageResponse(BaseModel):
    """Assistant dependency usage summary before destructive actions."""

    assistant_id: int
    active_session_count: int = 0
    related_log_count: int = 0
    has_dependencies: bool = False


class AssistantReorderRequest(BaseModel):
    """Assistant reorder payload."""

    assistant_ids: list[int] = Field(default_factory=list, min_length=1)


class AssistantBulkActionRequest(BaseModel):
    """Assistant bulk action payload."""

    assistant_ids: list[int] = Field(default_factory=list, min_length=1)
    action: Literal["enable", "disable", "delete"]
    force: bool = False


class AssistantBulkActionResponse(BaseModel):
    """Assistant bulk action result."""

    action: Literal["enable", "disable", "delete"]
    affected_ids: list[int] = Field(default_factory=list)
    affected_count: int = 0
