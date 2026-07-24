"""Stable contracts for dynamic, sequential business-tool execution."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ToolDecisionAction = Literal["call_tool", "complete", "clarify", "unsupported", "limit_reached"]
ToolStepStatus = Literal["success", "failed"]
ToolRunStatus = Literal[
    "success",
    "partial_success",
    "needs_input",
    "unsupported",
    "failed",
    "limit_reached",
]


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ToolDecision(BaseModel):
    action: ToolDecisionAction
    tool_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class ToolStep(BaseModel):
    index: int
    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ToolStepStatus
    data: dict[str, Any] | None = None
    error: ToolError | None = None
    duration_ms: int | None = None


class ToolRunResult(BaseModel):
    status: ToolRunStatus
    message: str
    steps: list[ToolStep] = Field(default_factory=list)
    successful_data: list[dict[str, Any]] = Field(default_factory=list)
