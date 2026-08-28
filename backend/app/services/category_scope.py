"""Helpers for resolving document category scopes."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentCategory


async def resolve_category_subtree_ids(db: AsyncSession, category_id: int) -> list[int]:
    """Return the category id plus every descendant category id."""

    resolved_ids: list[int] = []
    pending_ids = [category_id]
    seen_ids: set[int] = set()

    while pending_ids:
        current_ids = [item for item in pending_ids if item not in seen_ids]
        pending_ids = []
        if not current_ids:
            continue

        resolved_ids.extend(current_ids)
        seen_ids.update(current_ids)
        result = await db.execute(
            select(DocumentCategory.id).where(DocumentCategory.parent_id.in_(current_ids))
        )
        pending_ids.extend(int(item) for item in result.scalars().all())

    return resolved_ids
