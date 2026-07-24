"""Validation and compatibility mapping for planner decisions."""

from __future__ import annotations

from typing import Any

from app.agents.business_tools.schemas import ToolDecision


def parse_tool_decision(parsed: dict[str, Any]) -> ToolDecision:
    return ToolDecision.model_validate(parsed)
