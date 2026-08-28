"""AgentChat widget request and response schemas."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_context_object(value: dict, *, max_bytes: int) -> dict:
    key_count = 0

    def _walk(item, depth: int) -> None:
        nonlocal key_count
        if depth > 3:
            raise ValueError("Context cannot be nested deeper than 3 levels")
        if isinstance(item, dict):
            key_count += len(item)
            if key_count > 30:
                raise ValueError("Context cannot contain more than 30 fields")
            for key, child in item.items():
                if not isinstance(key, str) or not key.strip() or len(key) > 120:
                    raise ValueError("Context keys must be non-empty strings up to 120 characters")
                _walk(child, depth + 1)
        elif isinstance(item, list):
            if len(item) > 100:
                raise ValueError("Context arrays cannot contain more than 100 items")
            for child in item:
                _walk(child, depth + 1)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError("Context contains an unsupported value")

    _walk(value, 1)
    if len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")) > max_bytes:
        raise ValueError(f"Context cannot exceed {max_bytes} bytes")
    return value


class IntegrationPrincipal(BaseModel):
    external_user_id: str = Field(..., min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)


class IntegrationBootstrapCreate(BaseModel):
    principal: IntegrationPrincipal
    scope: dict = Field(default_factory=dict)
    initial_page_type: str | None = Field(default=None, max_length=120)

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: dict) -> dict:
        return _validate_context_object(value, max_bytes=4096)


class IntegrationWidgetConfig(BaseModel):
    version: str
    protocol_version: Literal["1"] = "1"


class IntegrationBootstrapResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    api_base_url: str
    widget: IntegrationWidgetConfig


class WidgetPageContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    page_type: str = Field(..., min_length=1, max_length=120)
    route_name: str | None = Field(default=None, max_length=160)
    route_path: str | None = Field(default=None, max_length=500)
    entity_type: str | None = Field(default=None, max_length=120)
    entity_id: str | None = Field(default=None, max_length=255)
    entity_name: str | None = Field(default=None, max_length=255)
    attributes: dict = Field(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def validate_attributes(cls, value: dict) -> dict:
        return _validate_context_object(value, max_bytes=8192)


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
