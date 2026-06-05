"""Document-category repository helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentCategory, KnowledgeBase
from app.repositories.access_scope import accessible_knowledge_base_condition
from app.services.category_scope import resolve_category_subtree_ids


@dataclass(slots=True)
class DocumentCategorySummary:
    """Category plus current-document count."""

    category: DocumentCategory
    document_count: int


class DocumentCategoryRepository:
    """Encapsulates document-category persistence."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def list_for_knowledge_base(
        self,
        knowledge_base_id: int,
    ) -> list[DocumentCategorySummary]:
        document_join_condition = (
            (Document.category_id == DocumentCategory.id)
            & Document.is_current.is_(True)
        )

        stmt = (
            select(
                DocumentCategory,
                func.count(Document.id).label("document_count"),
            )
            .join(
                KnowledgeBase,
                KnowledgeBase.id == DocumentCategory.knowledge_base_id,
            )
            .outerjoin(
                Document,
                document_join_condition,
            )
            .where(
                accessible_knowledge_base_condition(self.user_id),
                DocumentCategory.knowledge_base_id == knowledge_base_id,
            )
            .group_by(DocumentCategory.id)
            .order_by(DocumentCategory.name.asc(), DocumentCategory.id.asc())
        )
        result = await self.db.execute(stmt)
        return [
            DocumentCategorySummary(category=category, document_count=document_count or 0)
            for category, document_count in result.all()
        ]

    async def get_by_id(self, category_id: int) -> DocumentCategory | None:
        result = await self.db.execute(
            select(DocumentCategory)
            .join(KnowledgeBase, KnowledgeBase.id == DocumentCategory.knowledge_base_id)
            .where(
                DocumentCategory.id == category_id,
                accessible_knowledge_base_condition(self.user_id),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        *,
        knowledge_base_id: int,
        name: str,
        parent_id: int | None = None,
    ) -> DocumentCategory | None:
        normalized_name = name.strip()
        if not normalized_name:
            return None
        stmt = (
            select(DocumentCategory)
            .join(KnowledgeBase, KnowledgeBase.id == DocumentCategory.knowledge_base_id)
            .where(
                accessible_knowledge_base_condition(self.user_id),
                DocumentCategory.knowledge_base_id == knowledge_base_id,
                func.lower(DocumentCategory.name) == normalized_name.lower(),
            )
        )
        if parent_id is not None:
            stmt = stmt.where(DocumentCategory.parent_id == parent_id)
        else:
            stmt = stmt.where(DocumentCategory.parent_id.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        knowledge_base_id: int,
        name: str,
        parent_id: int | None = None,
    ) -> DocumentCategory:
        if parent_id is not None:
            parent = await self.get_by_id(parent_id)
            if not parent:
                raise ValueError("Parent category not found")
            if parent.knowledge_base_id != knowledge_base_id:
                raise ValueError("Parent category does not belong to the same knowledge base")
        category = DocumentCategory(
            knowledge_base_id=knowledge_base_id,
            parent_id=parent_id,
            name=name.strip(),
        )
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def get_or_create(
        self,
        *,
        knowledge_base_id: int,
        name: str,
        parent_id: int | None = None,
    ) -> DocumentCategory:
        existing = await self.get_by_name(
            knowledge_base_id=knowledge_base_id,
            name=name,
            parent_id=parent_id,
        )
        if existing:
            return existing
        return await self.create(knowledge_base_id=knowledge_base_id, name=name, parent_id=parent_id)

    async def update(
        self,
        category_id: int,
        *,
        name: str,
    ) -> DocumentCategory | None:
        category = await self.get_by_id(category_id)
        if not category:
            return None
        category.name = name.strip()
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def get_subcategory_ids(self, parent_id: int) -> list[int]:
        """Return all direct child category IDs for a given parent."""
        result = await self.db.execute(
            select(DocumentCategory.id).where(DocumentCategory.parent_id == parent_id)
        )
        return list(result.scalars().all())

    async def get_subtree_ids(self, category_id: int) -> list[int]:
        """Return the category ID plus all descendant IDs."""
        return await resolve_category_subtree_ids(self.db, category_id)

    async def delete(self, category_id: int) -> bool:
        category = await self.get_by_id(category_id)
        if not category:
            return False
        # Collect this category and all subcategory IDs
        all_ids = await self.get_subtree_ids(category_id)
        # Clear category_id on documents belonging to this category or subcategories
        await self.db.execute(
            update(Document)
            .where(Document.category_id.in_(all_ids))
            .values(category_id=None)
        )
        # Subcategories are auto-deleted by CASCADE on parent_id FK
        await self.db.delete(category)
        await self.db.commit()
        return True
