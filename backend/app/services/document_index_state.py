"""Shared document indexing state helpers."""

from __future__ import annotations

import hashlib
from typing import Literal

DocumentIndexStatus = Literal["queued", "processing", "indexed", "failed"]

INDEX_STATUS_QUEUED: DocumentIndexStatus = "queued"
INDEX_STATUS_PROCESSING: DocumentIndexStatus = "processing"
INDEX_STATUS_INDEXED: DocumentIndexStatus = "indexed"
INDEX_STATUS_FAILED: DocumentIndexStatus = "failed"

ACTIVE_INDEX_STATUSES: tuple[DocumentIndexStatus, ...] = (
    INDEX_STATUS_QUEUED,
    INDEX_STATUS_PROCESSING,
)


def compute_content_hash(content: str) -> str:
    """Return a deterministic hash used to detect stale indexing tasks."""
    return hashlib.md5((content or "").encode("utf-8")).hexdigest()


def is_indexed_status(status: str | None) -> bool:
    """Check whether a persisted indexing state is retrieval-ready."""
    return status == INDEX_STATUS_INDEXED
