"""AgentChat widget request and response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WidgetSessionCreate(BaseModel):
    product_code: str = Field(..., min_length=1, max_length=120)
    project_code: str = Field(..., min_length=1, max_length=120)
    app_code: str = Field(..., min_length=1, max_length=120)
    external_user_id: str = Field(..., min_length=1, max_length=255)
    external_user_name: str | None = Field(default=None, max_length=255)
    store_id: str | None = Field(default=None, max_length=120)
    initial_page_type: str | None = Field(default=None, max_length=120)


class WidgetSessionResponse(BaseModel):
    token: str
    expires_in_seconds: int


class WidgetPageContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    page_type: str = Field(..., min_length=1, max_length=120)
    route_name: str | None = Field(default=None, max_length=160)
    route_path: str | None = Field(default=None, max_length=500)
    entity_type: str | None = Field(default=None, max_length=120)
    entity_id: str | None = Field(default=None, max_length=255)
    entity_name: str | None = Field(default=None, max_length=255)


class WidgetChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)
    page_context: WidgetPageContext


class WidgetPageConfigResponse(BaseModel):
    page_type: str
    page_name: str
    page_description: str = ""
    assistant_intro: str = ""
    suggested_questions: list[str] = Field(default_factory=list)


class WidgetBootstrapResponse(BaseModel):
    project_name: str
    app_name: str
    assistant_name: str
    welcome_message: str | None = None
    placeholder_text: str | None = None
    suggested_prompts: list[str] = Field(default_factory=list)
    page_config: WidgetPageConfigResponse | None = None
