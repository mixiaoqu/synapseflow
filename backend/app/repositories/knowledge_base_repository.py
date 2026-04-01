"""Knowledge-base repository."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, KnowledgeBase


class KnowledgeBaseRepository:
    """Persists knowledge bases."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def list_with_count(
        self,
        *,
        team_id: int | None = None,
    ) -> list[tuple[KnowledgeBase, int]]:
        """List knowledge bases with latest-document counts."""
        stmt = (
            select(KnowledgeBase, func.count(Document.id).label("doc_count"))
            .outerjoin(
                Document,
                (Document.knowledge_base_id == KnowledgeBase.id)
                & (Document.is_latest.is_(True)),
            )
            .where(KnowledgeBase.user_id == self.user_id)
        )
        if team_id is not None:
            stmt = stmt.where(KnowledgeBase.team_id == team_id)
        stmt = stmt.group_by(KnowledgeBase.id).order_by(KnowledgeBase.created_at.desc())
        result = await self.db.execute(stmt)
        return [(knowledge_base, doc_count or 0) for knowledge_base, doc_count in result.all()]

    async def create(
        self,
        name: str,
        *,
        team_id: int = 1,
        description: str | None = None,
    ) -> KnowledgeBase:
        """Create a knowledge base."""
        knowledge_base = KnowledgeBase(
            user_id=self.user_id,
            team_id=team_id,
            name=name.strip(),
            description=(description or "").strip() or None,
        )
        self.db.add(knowledge_base)
        await self.db.commit()
        await self.db.refresh(knowledge_base)
        return knowledge_base

    async def get_by_id(self, knowledge_base_id: int) -> KnowledgeBase | None:
        """Fetch one knowledge base."""
        result = await self.db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == knowledge_base_id,
                KnowledgeBase.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        knowledge_base_id: int,
        *,
        name: str,
        description: str | None = None,
    ) -> KnowledgeBase | None:
        """Update knowledge-base fields."""
        knowledge_base = await self.get_by_id(knowledge_base_id)
        if not knowledge_base:
            return None
        knowledge_base.name = name.strip()
        knowledge_base.description = (description or "").strip() or None
        await self.db.commit()
        await self.db.refresh(knowledge_base)
        return knowledge_base

    async def delete(self, knowledge_base_id: int) -> bool:
        """Delete a knowledge base and detach its documents."""
        knowledge_base = await self.get_by_id(knowledge_base_id)
        if not knowledge_base:
            return False
        await self.db.execute(
            update(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .values(knowledge_base_id=None)
        )
        await self.db.delete(knowledge_base)
        await self.db.commit()
        return True
