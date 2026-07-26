"""Convert one business operation response into an immutable execution step."""

from __future__ import annotations

from typing import Any

from app.agents.business_ops.tools.schemas import ToolStep
from app.application.business_operations.schemas import BusinessOperationResult


def build_tool_step(
    *,
    index: int,
    tool_id: str,
    arguments: dict[str, Any],
    result: BusinessOperationResult,
) -> ToolStep:
    return ToolStep(
        index=index,
        tool_id=tool_id,
        arguments=arguments,
        status="success" if result.success else "failed",
        data=result.data,
        error=result.error.model_dump() if result.error else None,
        duration_ms=result.duration_ms,
    )
