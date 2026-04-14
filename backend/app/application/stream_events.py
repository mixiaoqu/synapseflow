"""Small helpers for rendering workflow SSE events."""

from __future__ import annotations

from typing import Any

from app.agents.runtime.events import AgentEventType, build_sse_envelope, render_sse_event

SYSTEM_NODE_ID = "system"
SYSTEM_NODE_NAME = "System"


def emit_event(
    event_type: AgentEventType | str,
    data: dict[str, Any],
    *,
    node_id: str = "",
    node_name: str = "",
    run_id: str | None = None,
) -> str:
    """Build and render a standard SSE event."""

    return render_sse_event(
        build_sse_envelope(
            event_type,
            data,
            node_id=node_id,
            node_name=node_name,
            run_id=run_id,
        )
    )


def emit_start(run_id: str | None, message: str) -> str:
    return emit_event(
        AgentEventType.START,
        {"message": message},
        node_id=SYSTEM_NODE_ID,
        node_name=SYSTEM_NODE_NAME,
        run_id=run_id,
    )


def emit_complete(run_id: str | None, data: dict[str, Any]) -> str:
    return emit_event(
        AgentEventType.COMPLETE,
        data,
        node_id=SYSTEM_NODE_ID,
        node_name=SYSTEM_NODE_NAME,
        run_id=run_id,
    )


def emit_error(run_id: str | None, message: str) -> str:
    return emit_event(
        AgentEventType.ERROR,
        {"message": message},
        node_id=SYSTEM_NODE_ID,
        node_name=SYSTEM_NODE_NAME,
        run_id=run_id,
    )


def emit_node_start(
    node_id: str,
    node_name: str,
    run_id: str | None,
    *,
    message: str,
) -> str:
    return emit_event(
        AgentEventType.NODE_START,
        {"message": message},
        node_id=node_id,
        node_name=node_name,
        run_id=run_id,
    )


def emit_node_complete(
    node_id: str,
    node_name: str,
    run_id: str | None,
    data: dict[str, Any],
) -> str:
    return emit_event(
        AgentEventType.NODE_COMPLETE,
        data,
        node_id=node_id,
        node_name=node_name,
        run_id=run_id,
    )
