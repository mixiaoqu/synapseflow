"""Schemas for controlled business data operations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

BusinessOperationRiskLevel = Literal["low", "medium", "high"]
BusinessOperationParamType = Literal[
    "text",
    "select",
    "number",
    "boolean",
    "array",
    "object",
]


class BusinessOperationParamSpec(BaseModel):
    key: str
    label: str
    type: BusinessOperationParamType = "text"
    required: bool = True
    description: str = ""
    resolver: str | None = None
    enum_values: list[Any] = Field(default_factory=list)
    default: Any = None


class BusinessOperationDefinition(BaseModel):
    id: str
    name: str
    description: str
    domain: str = "general"
    action: str = "execute"
    read_only: bool = False
    required_permissions: list[str] = Field(default_factory=list)
    typical_queries: list[str] = Field(default_factory=list)
    risk_level: BusinessOperationRiskLevel = "low"
    requires_confirmation: bool = False
    required_scope: list[str] = Field(default_factory=list)
    params: list[BusinessOperationParamSpec] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)


class BusinessOperationActor(BaseModel):
    user_id: int | None = None
    external_user_id: str | None = None
    external_user_name: str | None = None


class BusinessOperationRequest(BaseModel):
    operation_id: str
    project_app_id: int | None = None
    session_id: str | None = None
    actor: BusinessOperationActor = Field(default_factory=BusinessOperationActor)
    scope: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class BusinessOperationMissingField(BaseModel):
    key: str
    label: str
    type: BusinessOperationParamType = "text"
    required: bool = True
    description: str = ""
    resolver: str | None = None


class BusinessOperationErrorPayload(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class BusinessOperationResult(BaseModel):
    success: bool
    operation_id: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[BusinessOperationMissingField] = Field(default_factory=list)
    error: BusinessOperationErrorPayload | None = None
    http_status: int | None = None
    duration_ms: int | None = None
