"""Shared graph indexing state helpers."""

from __future__ import annotations

from typing import Literal

GraphIndexStatus = Literal["queued", "processing", "finalizing", "indexed", "failed"]

GRAPH_INDEX_STATUS_QUEUED: GraphIndexStatus = "queued"
GRAPH_INDEX_STATUS_PROCESSING: GraphIndexStatus = "processing"
GRAPH_INDEX_STATUS_FINALIZING: GraphIndexStatus = "finalizing"
GRAPH_INDEX_STATUS_INDEXED: GraphIndexStatus = "indexed"
GRAPH_INDEX_STATUS_FAILED: GraphIndexStatus = "failed"

ACTIVE_GRAPH_INDEX_STATUSES: tuple[GraphIndexStatus, ...] = (
    GRAPH_INDEX_STATUS_QUEUED,
    GRAPH_INDEX_STATUS_PROCESSING,
    GRAPH_INDEX_STATUS_FINALIZING,
)


def is_graph_indexed_status(status: str | None) -> bool:
    """Check whether a persisted graph-indexing state is ready."""
    return status == GRAPH_INDEX_STATUS_INDEXED
