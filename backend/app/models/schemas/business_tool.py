"""Schemas for business connections, APIs, tools, implementations and call logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BusinessToolMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
BusinessToolRiskLevel = Literal["low", "medium", "high"]
BusinessToolStatus = Literal["draft", "verified", "published", "error"]
BusinessConnectionEnvironment = Literal["development", "staging", "production"]
BusinessConnectionAuthType = Literal["none", "bearer", "header"]
BusinessConnectionStatus = Literal["untested", "available", "error"]
BusinessToolParamType = Literal["text", "number", "boolean", "array", "object"]
BusinessApiSourceType = Literal["manual", "openapi_imported"]
BusinessToolImplementationType = Literal["http"]
BusinessApiFieldType = Literal["string", "number", "boolean", "array", "object"]
BusinessApiRequestFieldLocation = Literal["query", "path", "header", "body"]


class BusinessApiRequestFieldSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=120)
    label: str = Field(..., min_length=1, max_length=100)
    location: BusinessApiRequestFieldLocation = Field("query", alias="in", serialization_alias="in")
    type: BusinessApiFieldType = "string"
    required: bool = False
    description: str = Field("", max_length=500)


class BusinessApiRequestSchema(BaseModel):
    fields: list[BusinessApiRequestFieldSpec] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_unique_fields(self):
        unique_keys = {(field.location, field.name) for field in self.fields}
        if len(unique_keys) != len(self.fields):
            raise ValueError("请求字段中存在重复的请求位置和字段名组合")
        return self


class BusinessApiResponseFieldSpec(BaseModel):
    path: str = Field(..., min_length=1, max_length=240)
    label: str = Field(..., min_length=1, max_length=100)
    type: BusinessApiFieldType = "string"
    required: bool = False
    description: str = Field("", max_length=500)


class BusinessApiResponseSchema(BaseModel):
    fields: list[BusinessApiResponseFieldSpec] = Field(default_factory=list, max_length=400)

    @model_validator(mode="after")
    def validate_unique_paths(self):
        unique_paths = {field.path for field in self.fields}
        if len(unique_paths) != len(self.fields):
            raise ValueError("响应字段中存在重复的字段路径")
        return self


class BusinessConnectionBase(BaseModel):
    team_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    environment: BusinessConnectionEnvironment = "production"
    base_url: str = Field(..., min_length=1, max_length=2000)
    auth_type: BusinessConnectionAuthType = "none"
    auth_secret_ref: str | None = Field(None, max_length=255)
    auth_header_name: str | None = Field(None, max_length=100)
    enabled: bool = True


class BusinessConnectionCreate(BusinessConnectionBase):
    pass


class BusinessConnectionUpdate(BusinessConnectionBase):
    pass


class BusinessConnectionResponse(BusinessConnectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_name: str | None = None
    status: BusinessConnectionStatus
    last_tested_at: datetime | None = None
    last_test_error: str | None = None
    tool_count: int = 0
    api_count: int = 0
    created_at: datetime
    updated_at: datetime


class BusinessConnectionListResponse(BaseModel):
    items: list[BusinessConnectionResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class BusinessConnectionTestResponse(BaseModel):
    success: bool
    status: BusinessConnectionStatus
    http_status: int | None = None
    duration_ms: int | None = None
    message: str


class BusinessToolParamSpec(BaseModel):
    key: str = Field(..., min_length=1, max_length=120)
    label: str = Field(..., min_length=1, max_length=100)
    type: BusinessToolParamType = "text"
    required: bool = False
    description: str = Field("", max_length=500)


class BusinessApiBase(BaseModel):
    team_id: int = Field(..., gt=0)
    connection_id: int = Field(..., gt=0)
    api_key: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=1000)
    method: BusinessToolMethod = "GET"
    path: str = Field(..., min_length=1, max_length=2000)
    request_schema: BusinessApiRequestSchema = Field(default_factory=BusinessApiRequestSchema)
    response_schema: BusinessApiResponseSchema = Field(default_factory=BusinessApiResponseSchema)
    source_type: BusinessApiSourceType = "manual"
    source_version: str | None = Field(None, max_length=100)
    enabled: bool = True


class BusinessApiCreate(BusinessApiBase):
    pass


class BusinessApiUpdate(BusinessApiBase):
    pass


class BusinessApiResponse(BusinessApiBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_name: str | None = None
    connection_name: str
    connection_environment: BusinessConnectionEnvironment
    connection_status: BusinessConnectionStatus
    created_at: datetime
    updated_at: datetime


class BusinessApiListResponse(BaseModel):
    items: list[BusinessApiResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class BusinessToolImplementationBase(BaseModel):
    business_api_id: int = Field(..., gt=0)
    implementation_type: BusinessToolImplementationType = "http"
    context_binding: dict[str, Any] = Field(default_factory=dict)
    request_mapping: dict[str, Any] = Field(default_factory=dict)
    response_mapping: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(100, ge=0, le=10000)
    enabled: bool = True


class BusinessToolImplementationCreate(BusinessToolImplementationBase):
    pass


class BusinessToolImplementationUpdate(BusinessToolImplementationBase):
    pass


class BusinessToolImplementationResponse(BusinessToolImplementationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_tool_id: int
    api_key: str
    api_name: str
    method: BusinessToolMethod
    path: str
    connection_id: int
    connection_name: str
    connection_environment: BusinessConnectionEnvironment
    connection_status: BusinessConnectionStatus
    status: BusinessToolStatus
    last_tested_at: datetime | None = None
    last_test_error: str | None = None
    created_at: datetime
    updated_at: datetime


class BusinessToolImplementationListResponse(BaseModel):
    items: list[BusinessToolImplementationResponse] = Field(default_factory=list)


class BusinessToolImplementationSummary(BaseModel):
    implementation_id: int
    business_api_id: int
    api_key: str
    api_name: str
    method: BusinessToolMethod
    path: str
    connection_id: int
    connection_name: str
    connection_environment: BusinessConnectionEnvironment
    connection_status: BusinessConnectionStatus
    implementation_status: BusinessToolStatus
    enabled: bool
    priority: int


class BusinessToolBase(BaseModel):
    team_id: int = Field(..., gt=0)
    tool_key: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1000)
    typical_queries: list[str] = Field(default_factory=list, max_length=20)
    params_schema: list[BusinessToolParamSpec] = Field(default_factory=list, max_length=50)
    risk_level: BusinessToolRiskLevel = "low"
    requires_confirmation: bool = False
    enabled: bool = True


class BusinessToolCreate(BusinessToolBase):
    pass


class BusinessToolUpdate(BusinessToolBase):
    pass


class BusinessToolResponse(BusinessToolBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_name: str | None = None
    status: BusinessToolStatus
    last_tested_at: datetime | None = None
    last_test_error: str | None = None
    implementation_count: int = 0
    primary_implementation: BusinessToolImplementationSummary | None = None
    created_at: datetime
    updated_at: datetime


class BusinessToolListResponse(BaseModel):
    items: list[BusinessToolResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class BusinessToolTestRequest(BaseModel):
    implementation_id: int | None = Field(None, gt=0)
    scope: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class BusinessToolTestResponse(BaseModel):
    success: bool
    status: BusinessToolStatus
    implementation_id: int | None = None
    http_status: int | None = None
    duration_ms: int | None = None
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None


class BusinessToolPublishResponse(BaseModel):
    id: int
    status: BusinessToolStatus
    published_implementation_ids: list[int] = Field(default_factory=list)
    message: str


class ProjectAppBusinessToolBindingCreate(BaseModel):
    business_tool_id: int = Field(..., gt=0)
    enabled: bool = True


class ProjectAppBusinessToolBindingResponse(BaseModel):
    id: int
    project_app_id: int
    business_tool_id: int
    tool_key: str
    name: str
    description: str | None = None
    risk_level: BusinessToolRiskLevel
    status: BusinessToolStatus
    enabled: bool
    tool_enabled: bool
    is_available: bool
    unavailable_reason: str | None = None
    primary_implementation: BusinessToolImplementationSummary | None = None
    created_at: datetime
    updated_at: datetime


class ProjectAppBusinessToolBindingListResponse(BaseModel):
    items: list[ProjectAppBusinessToolBindingResponse] = Field(default_factory=list)


class BusinessToolCallLogResponse(BaseModel):
    id: int
    team_id: int
    team_name: str | None = None
    project_app_id: int | None = None
    project_app_name: str | None = None
    business_tool_id: int | None = None
    business_api_id: int | None = None
    business_tool_implementation_id: int | None = None
    tool_key: str
    tool_name: str
    api_key: str | None = None
    api_name: str | None = None
    session_id: str | None = None
    external_user_id: str | None = None
    status: str
    http_status: int | None = None
    duration_ms: int | None = None
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_payload: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime


class BusinessToolCallLogListResponse(BaseModel):
    items: list[BusinessToolCallLogResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
