"""Base helpers shared by agent application services."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from app.agents.runtime import (
    AgentEventType,
    BaseAgentContext,
    build_base_agent_context,
    build_sse_envelope,
    merge_agent_state,
)


class BaseAgentService:
    """Common helpers for building workflow state and SSE events."""

    @staticmethod
    def _new_run_id() -> str:
        return uuid4().hex

    def build_context(
        self,
        *,
        user_id: int | None = None,
        team_id: int | None = None,
        knowledge_base_id: int | None = None,
        request_id: str | None = None,
        run_id: str | None = None,
        messages: list[Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> BaseAgentContext:
        """Build the shared runtime context."""

        return build_base_agent_context(
            user_id=user_id,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            request_id=request_id,
            run_id=run_id or self._new_run_id(),
            messages=messages,
            metadata=metadata,
        )

    @staticmethod
    def build_state(
        context: BaseAgentContext,
        extra_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Merge shared context with workflow-specific state."""

        return merge_agent_state(context, extra_state)

    @staticmethod
    def make_event(
        event_type: AgentEventType | str,
        data: dict[str, Any],
        *,
        node_id: str = "",
        node_name: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Build an SSE envelope."""

        return build_sse_envelope(
            event_type,
            data,
            node_id=node_id,
            node_name=node_name,
            run_id=run_id,
        )
