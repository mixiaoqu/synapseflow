"""Helpers for emitting optional LangGraph custom stream events."""

from __future__ import annotations

from typing import Any, Callable


StreamWriter = Callable[[dict[str, Any]], None]


def get_optional_stream_writer() -> StreamWriter | None:
    """Return LangGraph's stream writer when available inside graph streaming."""

    try:
        from langgraph.config import get_stream_writer
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return None

    try:
        return get_stream_writer()
    except RuntimeError:  # pragma: no cover - no active graph stream context
        return None


def emit_progress(
    writer: StreamWriter | None,
    *,
    workflow_id: str,
    node_id: str,
    message: str,
    stage: str,
    **data: Any,
) -> None:
    """Emit a non-fatal progress event when graph streaming is active."""

    if writer is None:
        return
    writer(
        {
            "type": "progress",
            "workflow_id": workflow_id,
            "node_id": node_id,
            "stage": stage,
            "message": message,
            **data,
        }
    )


def emit_activity(
    writer: StreamWriter | None,
    *,
    workflow_id: str,
    node_id: str,
    stage: str,
    message: str,
    display_stage: str,
    display_title: str,
    activity_text: str,
    activity_status: str = "running",
    **data: Any,
) -> None:
    """Emit progress with user-facing stage and activity metadata."""

    emit_progress(
        writer,
        workflow_id=workflow_id,
        node_id=node_id,
        stage=stage,
        message=message,
        display_stage=display_stage,
        display_title=display_title,
        activity_text=activity_text,
        activity_status=activity_status,
        **data,
    )
