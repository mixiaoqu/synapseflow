"""Document-category repository helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentCategory, KnowledgeBase


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
                (Document.category_id == DocumentCategory.id) & Document.is_current.is_(True),
            )
            .where(
                KnowledgeBase.user_id == self.user_id,
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
                KnowledgeBase.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        *,
        knowledge_base_id: int,
        name: str,
    ) -> DocumentCategory | None:
        normalized_name = name.strip()
        if not normalized_name:
            return None
        result = await self.db.execute(
            select(DocumentCategory)
            .join(KnowledgeBase, KnowledgeBase.id == DocumentCategory.knowledge_base_id)
            .where(
                KnowledgeBase.user_id == self.user_id,
                DocumentCategory.knowledge_base_id == knowledge_base_id,
                func.lower(DocumentCategory.name) == normalized_name.lower(),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        knowledge_base_id: int,
        name: str,
    ) -> DocumentCategory:
        category = DocumentCategory(
            knowledge_base_id=knowledge_base_id,
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
    ) -> DocumentCategory:
        existing = await self.get_by_name(
            knowledge_base_id=knowledge_base_id,
            name=name,
        )
        if existing:
            return existing
        return await self.create(knowledge_base_id=knowledge_base_id, name=name)

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

    async def delete(self, category_id: int) -> bool:
        category = await self.get_by_id(category_id)
        if not category:
            return False
        await self.db.execute(
            update(Document)
            .where(Document.category_id == category_id)
            .values(category_id=None)
        )
        await self.db.delete(category)
        await self.db.commit()
        return True
