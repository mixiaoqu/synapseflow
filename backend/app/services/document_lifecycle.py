"""Document lifecycle status constants and helpers."""

from __future__ import annotations

DOC_STATUS_DRAFT = "draft"
DOC_STATUS_INDEXED = "indexed"
DOC_STATUS_PENDING_REVIEW = "pending_review"
DOC_STATUS_APPROVED = "approved"
DOC_STATUS_PUBLISHED = "published"
DOC_STATUS_ARCHIVED = "archived"

EDITABLE_DOCUMENT_STATUSES: tuple[str, ...] = (
    DOC_STATUS_DRAFT,
    DOC_STATUS_INDEXED,
    DOC_STATUS_APPROVED,
)
REVIEWABLE_DOCUMENT_STATUSES: tuple[str, ...] = (
    DOC_STATUS_DRAFT,
    DOC_STATUS_INDEXED,
    DOC_STATUS_PENDING_REVIEW,
    DOC_STATUS_APPROVED,
    DOC_STATUS_PUBLISHED,
)
VISIBLE_ASK_DOCUMENT_STATUSES: tuple[str, ...] = (DOC_STATUS_PUBLISHED,)
