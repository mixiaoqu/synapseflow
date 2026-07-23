"""Schemas for tool providers, governed tools, grants and invocations."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TransportType = Literal["business_http", "mcp_http"]
ProviderHealthStatus = Literal["untested", "available", "error"]
PublishStatus = Literal["draft", "published", "needs_review"]
SyncStatus = Literal["active", "removed", "invalid"]
RiskLevel = Literal["low", "medium", "high"]


class ToolProviderCreate(BaseModel):
    team_id: int = Field(..., gt=0)
    code: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    base_url: str = Field(..., min_length=1)
    transport_type: TransportType = "business_http"
    auth_type: Literal["none", "bearer", "header"] = "bearer"
    auth_header_name: str | None = Field(default=None, max_length=100)
    auth_token: str | None = Field(default=None, min_length=16, max_length=4096)
    enabled: bool = True


class ToolProviderUpdate(BaseModel):
    team_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    base_url: str = Field(..., min_length=1)
    transport_type: TransportType
    auth_type: Literal["none", "bearer", "header"]
    auth_header_name: str | None = Field(default=None, max_length=100)
    auth_token: str | None = Field(default=None, min_length=16, max_length=4096)
    enabled: bool = True


class ToolProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    team_name: str | None = None
    code: str
    name: str
    description: str | None = None
    base_url: str
    transport_type: str
    auth_type: str
    auth_header_name: str | None = None
    has_auth_token: bool = False
    auth_token_masked: str | None = None
    enabled: bool
    health_status: str
    last_checked_at: datetime | None = None
    last_error: str | None = None
    tool_count: int = 0
    created_at: datetime
    updated_at: datetime


class ToolProviderListResponse(BaseModel):
    items: list[ToolProviderResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class ToolProviderTestResponse(BaseModel):
    success: bool
    health_status: str
    message: str
    duration_ms: int | None = None
    tool_count: int = 0


class AgentToolSyncResponse(BaseModel):
    provider_id: int
    synced_count: int
    message: str


class AgentToolUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    agent_description: str | None = None
    risk_level: RiskLevel = "low"
    requires_confirmation: bool = False


class AgentToolTestRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentToolTestResponse(BaseModel):
    success: bool
    message: str
    duration_ms: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None


class AgentToolPublishResponse(BaseModel):
    id: int
    publish_status: str
    message: str


class AgentToolBatchPublishRequest(BaseModel):
    tool_ids: list[Annotated[int, Field(gt=0)]] = Field(..., min_length=1, max_length=100)


class AgentToolBatchPublishResponse(BaseModel):
    published_ids: list[int] = Field(default_factory=list)
    published_count: int = 0
    message: str


class AgentToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    provider_code: str
    provider_name: str
    team_id: int
    team_name: str | None = None
    external_name: str
    external_display_name: str
    external_description: str | None = None
    domain: str
    action: str
    read_only: bool
    required_permissions: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    required_context: list[str] = Field(default_factory=list)
    schema_hash: str
    sync_status: str
    last_synced_at: datetime | None = None
    tool_key: str
    name: str
    agent_description: str | None = None
    risk_level: str
    requires_confirmation: bool
    publish_status: str
    approved_schema_hash: str | None = None
    last_tested_at: datetime | None = None
    last_test_error: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentToolListResponse(BaseModel):
    items: list[AgentToolResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class AgentToolGrantCreate(BaseModel):
    agent_tool_id: int = Field(..., gt=0)


class AgentToolGrantReplace(BaseModel):
    agent_tool_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list)


class AgentToolGrantResponse(BaseModel):
    id: int
    project_app_id: int
    agent_tool_id: int
    tool_key: str
    tool_name: str
    provider_id: int
    provider_name: str
    created_at: datetime


class AgentToolGrantListResponse(BaseModel):
    items: list[AgentToolGrantResponse] = Field(default_factory=list)


class AgentToolInvocationResponse(BaseModel):
    id: int
    team_id: int
    team_name: str | None = None
    provider_id: int | None = None
    provider_name: str | None = None
    provider_code: str
    project_app_id: int | None = None
    project_app_name: str | None = None
    agent_tool_id: int | None = None
    external_name: str
    tool_key: str
    schema_hash: str
    session_id: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    actor_user_id: int | None = None
    external_user_id: str | None = None
    call_source: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    request_summary: dict[str, Any] = Field(default_factory=dict)
    response_summary: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool
    confirmed_at: datetime | None = None
    created_at: datetime


class AgentToolInvocationListResponse(BaseModel):
    items: list[AgentToolInvocationResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
