"""Project and embedded application schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ProjectAppTerminalType = Literal["web", "h5", "mini_program", "admin", "api", "other"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    team_id: int = Field(..., gt=0)
    product_id: int = Field(..., gt=0)
    description: str | None = None
    is_active: bool = True


class ProjectUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    team_id: int = Field(..., gt=0)
    product_id: int = Field(..., gt=0)
    description: str | None = None
    is_active: bool = True


class ProjectCopy(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    is_active: bool = False


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    team_name: str | None = None
    product_id: int
    product_code: str | None = None
    product_name: str | None = None
    code: str
    name: str
    description: str | None = None
    is_active: bool
    app_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class ProjectBulkActionRequest(BaseModel):
    project_ids: list[int] = Field(default_factory=list, min_length=1)
    action: Literal["enable", "disable", "delete"]


class ProjectBulkActionResponse(BaseModel):
    action: Literal["enable", "disable", "delete"]
    affected_ids: list[int] = Field(default_factory=list)
    affected_count: int = 0


class ProjectAppCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    knowledge_base_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    default_assistant_id: int | None = Field(default=None, gt=0)
    terminal_type: ProjectAppTerminalType = "web"
    is_active: bool = True


class ProjectAppUpdate(BaseModel):
    code: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    knowledge_base_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    default_assistant_id: int | None = Field(default=None, gt=0)
    terminal_type: ProjectAppTerminalType = "web"
    is_active: bool = True


class ProjectAppResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    code: str
    name: str
    description: str | None = None
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    default_assistant_id: int | None = None
    default_assistant_name: str | None = None
    terminal_type: ProjectAppTerminalType = "web"
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectAppListResponse(BaseModel):
    items: list[ProjectAppResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class ProjectAppBulkActionRequest(BaseModel):
    app_ids: list[int] = Field(default_factory=list, min_length=1)
    action: Literal["enable", "disable", "delete"]


class ProjectAppBulkActionResponse(BaseModel):
    action: Literal["enable", "disable", "delete"]
    affected_ids: list[int] = Field(default_factory=list)
    affected_count: int = 0


class EmbedSessionCreate(BaseModel):
    product_code: str = Field(..., min_length=1, max_length=120)
    project_code: str = Field(..., min_length=1, max_length=120)
    app_code: str = Field(..., min_length=1, max_length=120)
    external_user_id: str = Field(..., min_length=1, max_length=255)
    external_user_name: str | None = Field(default=None, max_length=255)
    store_id: str | None = Field(default=None, max_length=120)
    initial_page_type: str | None = Field(default=None, max_length=120)


class ProjectAppEmbedPreviewCreate(BaseModel):
    store_id: str | None = Field(default=None, max_length=120)


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
    product_id: int
    product_code: str
    product_name: str
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
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbedAssistantChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)
    page_context: EmbedPageContext | None = None
