"""Agent integration schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

McpServerStatus = Literal["untested", "available", "error"]
AgentToolStatus = Literal["draft", "verified", "published", "error"]
RiskLevel = Literal["low", "medium", "high"]


class McpServerCreate(BaseModel):
    team_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    environment: str = Field("production", min_length=1, max_length=30)
    endpoint_url: str = Field(..., min_length=1)
    transport_type: str = Field("http", min_length=1, max_length=30)
    auth_type: str = Field("none", min_length=1, max_length=20)
    auth_token: str | None = Field(default=None, min_length=16, max_length=4096)
    auth_header_name: str | None = None
    enabled: bool = True


class McpServerUpdate(BaseModel):
    team_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    environment: str = Field("production", min_length=1, max_length=30)
    endpoint_url: str = Field(..., min_length=1)
    transport_type: str = Field("http", min_length=1, max_length=30)
    auth_type: str = Field("none", min_length=1, max_length=20)
    auth_token: str | None = Field(default=None, min_length=16, max_length=4096)
    auth_header_name: str | None = None
    enabled: bool = True


class McpServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    team_name: str | None = None
    name: str
    description: str | None = None
    environment: str
    endpoint_url: str
    transport_type: str
    auth_type: str
    auth_header_name: str | None = None
    has_auth_token: bool = False
    auth_token_masked: str | None = None
    enabled: bool
    status: str
    last_checked_at: datetime | None = None
    last_error: str | None = None
    tool_count: int = 0
    created_at: datetime
    updated_at: datetime


class McpServerListResponse(BaseModel):
    items: list[McpServerResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class McpServerTestResponse(BaseModel):
    success: bool
    status: str
    message: str
    duration_ms: int | None = None
    tool_count: int = 0


class McpToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mcp_server_id: int
    server_name: str | None = None
    raw_name: str
    raw_description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    schema_hash: str
    sync_status: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    last_synced_at: datetime | None = None
    agent_tool_id: int | None = None
    agent_tool_status: str | None = None
    agent_tool_enabled: bool = False
    created_at: datetime
    updated_at: datetime


class McpToolListResponse(BaseModel):
    items: list[McpToolResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class McpToolSyncResponse(BaseModel):
    server_id: int
    synced_count: int
    message: str


class McpToolEnabledUpdate(BaseModel):
    enabled: bool


class AgentToolCreate(BaseModel):
    team_id: int = Field(..., gt=0)
    mcp_tool_id: int = Field(..., gt=0)
    tool_key: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    agent_description: str | None = None
    params_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = "low"
    requires_confirmation: bool = False
    enabled: bool = True


class AgentToolUpdate(BaseModel):
    team_id: int = Field(..., gt=0)
    mcp_tool_id: int = Field(..., gt=0)
    tool_key: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    agent_description: str | None = None
    params_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = "low"
    requires_confirmation: bool = False
    enabled: bool = True


class AgentToolTestRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentToolTestResponse(BaseModel):
    success: bool
    status: str
    message: str
    duration_ms: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class AgentToolPublishResponse(BaseModel):
    id: int
    status: str
    message: str


class AgentToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    team_name: str | None = None
    mcp_tool_id: int
    mcp_server_id: int | None = None
    mcp_server_name: str | None = None
    mcp_tool_name: str | None = None
    tool_key: str
    name: str
    description: str | None = None
    agent_description: str | None = None
    params_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] = Field(default_factory=dict)
    tool_type: str
    risk_level: str
    requires_confirmation: bool
    enabled: bool
    status: str
    last_tested_at: datetime | None = None
    last_test_error: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentToolListResponse(BaseModel):
    items: list[AgentToolResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class AgentAppToolSetBindingCreate(BaseModel):
    mcp_server_id: int = Field(..., gt=0)
    enabled: bool = True


class AgentAppToolSetBindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_app_id: int
    mcp_server_id: int
    mcp_server_name: str
    mcp_server_description: str | None = None
    tool_count: int = 0
    enabled: bool
    unavailable_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentAppToolSetBindingListResponse(BaseModel):
    items: list[AgentAppToolSetBindingResponse] = Field(default_factory=list)


class ProjectAppAccessCreate(BaseModel):
    allowed_origins: list[str] = Field(..., min_length=1, max_length=20)


class ProjectAppAccessUpdate(BaseModel):
    allowed_origins: list[str] = Field(..., min_length=1, max_length=20)


class ProjectAppAccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_app_id: int
    client_id: str
    client_secret_last_four: str
    allowed_origins: list[str] = Field(default_factory=list)
    token_version: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ProjectAppAccessIssuedResponse(ProjectAppAccessResponse):
    client_secret: str


class AgentToolCallLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    team_name: str | None = None
    project_app_id: int | None = None
    project_app_name: str | None = None
    agent_tool_id: int | None = None
    mcp_server_id: int | None = None
    mcp_server_name: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    actor_user_id: int | None = None
    external_user_id: str | None = None
    tool_key: str
    mcp_tool_name: str
    status: str
    duration_ms: int | None = None
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_payload: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    confirmed: bool
    confirmed_at: datetime | None = None
    created_at: datetime


class AgentToolCallLogListResponse(BaseModel):
    items: list[AgentToolCallLogResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
