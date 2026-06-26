"""Helpers for resolving graph retrieval document scopes."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.db.models import Document, KnowledgeBase
from app.db.session import AsyncSessionLocal
from app.repositories.access_scope import accessible_document_condition
from app.services.category_scope import resolve_category_subtree_ids


async def resolve_graph_category_document_ids(
    *,
    team_id: int | None,
    knowledge_base_id: int,
    category_id: int | None,
    user_id: int | None,
    document_statuses: Sequence[str] | None = None,
) -> list[int] | None:
    """Return current document ids in the selected category subtree for graph retrieval."""

    if category_id is None:
        return None

    async with AsyncSessionLocal() as db:
        category_ids = await resolve_category_subtree_ids(db, category_id)
        if not category_ids:
            return []

        stmt = (
            select(Document.id)
            .join(KnowledgeBase, KnowledgeBase.id == Document.knowledge_base_id)
            .where(
                Document.is_current.is_(True),
                Document.knowledge_base_id == knowledge_base_id,
                Document.category_id.in_(category_ids),
            )
            .order_by(Document.id.asc())
        )
        if team_id is not None:
            stmt = stmt.where(KnowledgeBase.team_id == team_id)
        if user_id is not None:
            stmt = stmt.where(accessible_document_condition(user_id))
        if document_statuses:
            stmt = stmt.where(Document.status.in_(list(document_statuses)))

        result = await db.execute(stmt)
        return [int(document_id) for document_id in result.scalars().all()]
