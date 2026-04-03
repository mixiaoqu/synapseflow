"""Standardized SSE envelopes shared by agent services."""

from __future__ import annotations

import json
import time
from enum import Enum
from typing import Any, TypedDict

SSE_EVENT_NAME = "message"


class AgentEventType(str, Enum):
    """Canonical stream event types emitted by SynapseFlow agents."""

    START = "start"
    PROGRESS = "progress"
    LOG = "log"
    NODE_START = "node_start"
    NODE_COMPLETE = "node_complete"
    ERROR = "error"
    COMPLETE = "complete"
    RETRIEVED = "retrieved"
    TOKEN = "token"


class SseEnvelope(TypedDict, total=False):
    """Payload shape returned by every streaming endpoint."""

    type: str
    node_id: str
    node_name: str
    timestamp: float
    data: dict[str, Any]
    run_id: str | None


def build_sse_envelope(
    event_type: AgentEventType | str,
    data: dict[str, Any],
    *,
    node_id: str = "",
    node_name: str = "",
    run_id: str | None = None,
    timestamp: float | None = None,
) -> SseEnvelope:
    """Construct a standardized stream envelope."""

    event_name = event_type.value if isinstance(event_type, AgentEventType) else str(event_type)
    return {
        "type": event_name,
        "node_id": node_id,
        "node_name": node_name,
        "timestamp": time.time() if timestamp is None else timestamp,
        "data": data,
        "run_id": run_id,
    }


def render_sse_event(
    envelope: SseEnvelope,
    *,
    event_name: str = SSE_EVENT_NAME,
) -> str:
    """Serialize a stream envelope into SSE wire format."""

    return "event: %s\ndata: %s\n\n" % (
        event_name,
        json.dumps(envelope, ensure_ascii=False),
    )
