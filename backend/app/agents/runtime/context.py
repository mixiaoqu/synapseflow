"""Shared runtime context for agent services and graph states."""

from __future__ import annotations

from typing import Annotated, Any, Mapping, MutableMapping, Optional, TypedDict

try:
    from langgraph.graph.message import add_messages
except ModuleNotFoundError:  # pragma: no cover - optional dependency fallback
    def add_messages(current: list[Any], new: list[Any]) -> list[Any]:
        return list(current or []) + list(new or [])


class BaseAgentContext(TypedDict, total=False):
    """Common context fields shared by every agent workflow."""

    messages: Annotated[list[Any], add_messages]
    user_id: Optional[int]
    team_id: Optional[int]
    knowledge_base_id: Optional[int]
    category_id: Optional[int]
    request_id: Optional[str]
    run_id: Optional[str]
    metadata: dict[str, Any]


def build_base_agent_context(
    *,
    user_id: int | None = None,
    team_id: int | None = None,
    knowledge_base_id: int | None = None,
    category_id: int | None = None,
    request_id: str | None = None,
    run_id: str | None = None,
    messages: list[Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> BaseAgentContext:
    """Create the shared runtime context used by agent services."""

    return {
        "messages": list(messages or []),
        "user_id": user_id,
        "team_id": team_id,
        "knowledge_base_id": knowledge_base_id,
        "category_id": category_id,
        "request_id": request_id,
        "run_id": run_id,
        "metadata": dict(metadata or {}),
    }


def merge_agent_state(
    context: BaseAgentContext,
    extra_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge shared context with workflow-specific state."""

    merged: MutableMapping[str, Any] = dict(context)
    if extra_state:
        merged.update(extra_state)
    return dict(merged)
