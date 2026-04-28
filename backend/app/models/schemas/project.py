"""Project and embedded application schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    team_id: int = Field(..., gt=0)
    description: str | None = None
    is_active: bool = True


class ProjectUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    team_id: int = Field(..., gt=0)
    description: str | None = None
    is_active: bool = True


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    team_name: str | None = None
    code: str
    name: str
    description: str | None = None
    is_active: bool
    app_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProjectAppCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    default_assistant_id: int | None = Field(default=None, gt=0)
    is_active: bool = True


class ProjectAppUpdate(BaseModel):
    code: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    default_assistant_id: int | None = Field(default=None, gt=0)
    is_active: bool = True


class ProjectAppResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    code: str
    name: str
    description: str | None = None
    default_assistant_id: int | None = None
    default_assistant_name: str | None = None
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EmbedSessionCreate(BaseModel):
    project_code: str = Field(..., min_length=1, max_length=120)
    app_code: str = Field(..., min_length=1, max_length=120)
    external_user_id: str = Field(..., min_length=1, max_length=255)
    external_user_name: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default=None, max_length=80)
    initial_page_type: str | None = Field(default=None, max_length=120)


class EmbedSessionResponse(BaseModel):
    embed_url: str
    expires_in_seconds: int


class EmbedPageConfigResponse(BaseModel):
    page_type: str
    page_name: str
    page_description: str = ""
    assistant_intro: str = ""
    suggested_questions: list[str] = Field(default_factory=list)


class EmbedAssistantBootstrapResponse(BaseModel):
    project_id: int
    project_code: str
    project_name: str
    project_app_id: int
    app_code: str
    app_name: str
    assistant_id: int
    assistant_name: str
    welcome_message: str | None = None
    placeholder_text: str | None = None
    suggested_prompts: list[str] = Field(default_factory=list)
    page_config: EmbedPageConfigResponse | None = None


class EmbedPageContext(BaseModel):
    app_id: str | None = Field(default=None, max_length=120)
    page_type: str = Field(..., min_length=1, max_length=120)


class EmbedAssistantChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)
    page_context: EmbedPageContext | None = None
