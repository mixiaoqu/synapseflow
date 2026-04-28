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
            "node_id": node_id,
            "stage": stage,
            "message": message,
            **data,
        }
    )
