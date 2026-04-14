"""Knowledge-base repository."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, KnowledgeBase
from app.repositories.access_scope import accessible_knowledge_base_condition
from app.services.document_index_state import (
    INDEX_STATUS_FAILED,
    INDEX_STATUS_INDEXED,
    INDEX_STATUS_PROCESSING,
    INDEX_STATUS_QUEUED,
)


@dataclass(slots=True)
class KnowledgeBaseRecentDocumentRecord:
    """Recent document summary for knowledge-base cards."""

    id: int
    title: str
    document_type: str | None
    size: int
    indexed: bool
    index_status: str
    index_error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class KnowledgeBaseSummaryRecord:
    """Aggregated knowledge-base summary for the dashboard."""

    knowledge_base: KnowledgeBase
    document_count: int
    indexed_document_count: int
    queued_document_count: int
    processing_document_count: int
    failed_document_count: int
    unindexed_document_count: int
    last_document_updated_at: datetime | None
    last_uploaded_at: datetime | None
    recent_documents: list[KnowledgeBaseRecentDocumentRecord]


class KnowledgeBaseRepository:
    """Persists knowledge bases."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def list_with_count(
        self,
        *,
        team_id: int | None = None,
    ) -> list[KnowledgeBaseSummaryRecord]:
        """List knowledge bases with dashboard summary metrics."""
        indexed_count = func.sum(case((Document.index_status == INDEX_STATUS_INDEXED, 1), else_=0))
        queued_count = func.sum(case((Document.index_status == INDEX_STATUS_QUEUED, 1), else_=0))
        processing_count = func.sum(
            case((Document.index_status == INDEX_STATUS_PROCESSING, 1), else_=0)
        )
        failed_count = func.sum(case((Document.index_status == INDEX_STATUS_FAILED, 1), else_=0))
        unindexed_count = func.sum(
            case(
                (
                    Document.id.is_not(None) & (Document.index_status != INDEX_STATUS_INDEXED),
                    1,
                ),
                else_=0,
            )
        )
        stmt = (
            select(
                KnowledgeBase,
                func.count(Document.id).label("doc_count"),
                indexed_count.label("indexed_doc_count"),
                queued_count.label("queued_doc_count"),
                processing_count.label("processing_doc_count"),
                failed_count.label("failed_doc_count"),
                unindexed_count.label("unindexed_doc_count"),
                func.max(Document.updated_at).label("last_document_updated_at"),
                func.max(Document.created_at).label("last_uploaded_at"),
            )
            .outerjoin(
                Document,
                (Document.knowledge_base_id == KnowledgeBase.id)
                & (Document.is_current.is_(True)),
            )
            .where(accessible_knowledge_base_condition(self.user_id))
        )
        if team_id is not None:
            stmt = stmt.where(KnowledgeBase.team_id == team_id)
        stmt = stmt.group_by(KnowledgeBase.id).order_by(KnowledgeBase.created_at.desc())
        result = await self.db.execute(stmt)
        rows = result.all()
        knowledge_base_ids = [knowledge_base.id for knowledge_base, *_ in rows]
        recent_docs_map = await self._list_recent_documents(knowledge_base_ids)
        return [
            KnowledgeBaseSummaryRecord(
                knowledge_base=knowledge_base,
                document_count=doc_count or 0,
                indexed_document_count=indexed_doc_count or 0,
                queued_document_count=queued_doc_count or 0,
                processing_document_count=processing_doc_count or 0,
                failed_document_count=failed_doc_count or 0,
                unindexed_document_count=unindexed_doc_count or 0,
                last_document_updated_at=last_document_updated_at,
                last_uploaded_at=last_uploaded_at,
                recent_documents=recent_docs_map.get(knowledge_base.id, []),
            )
            for (
                knowledge_base,
                doc_count,
                indexed_doc_count,
                queued_doc_count,
                processing_doc_count,
                failed_doc_count,
                unindexed_doc_count,
                last_document_updated_at,
                last_uploaded_at,
            ) in rows
        ]

    async def _list_recent_documents(
        self,
        knowledge_base_ids: list[int],
    ) -> dict[int, list[KnowledgeBaseRecentDocumentRecord]]:
        """Return the latest three current documents for each knowledge base."""
        if not knowledge_base_ids:
            return {}

        ranked_documents = (
            select(
                Document.knowledge_base_id.label("knowledge_base_id"),
                Document.id.label("id"),
                Document.title.label("title"),
                Document.document_type.label("document_type"),
                Document.size.label("size"),
                Document.created_at.label("created_at"),
                Document.updated_at.label("updated_at"),
                (Document.index_status == INDEX_STATUS_INDEXED).label("indexed"),
                Document.index_status.label("index_status"),
                Document.index_error.label("index_error"),
                func.row_number()
                .over(
                    partition_by=Document.knowledge_base_id,
                    order_by=(Document.created_at.desc(), Document.id.desc()),
                )
                .label("row_num"),
            )
            .where(
                Document.is_current.is_(True),
                Document.knowledge_base_id.in_(knowledge_base_ids),
            )
            .subquery()
        )

        stmt = (
            select(ranked_documents)
            .where(ranked_documents.c.row_num <= 3)
            .order_by(
                ranked_documents.c.knowledge_base_id.asc(),
                ranked_documents.c.created_at.desc(),
                ranked_documents.c.id.desc(),
            )
        )
        result = await self.db.execute(stmt)
        recent_docs_map: dict[int, list[KnowledgeBaseRecentDocumentRecord]] = {}
        for row in result:
            knowledge_base_id = row.knowledge_base_id
            if knowledge_base_id is None:
                continue
            recent_docs_map.setdefault(knowledge_base_id, []).append(
                KnowledgeBaseRecentDocumentRecord(
                    id=row.id,
                    title=row.title,
                    document_type=row.document_type,
                    size=row.size or 0,
                    indexed=bool(row.indexed),
                    index_status=row.index_status or INDEX_STATUS_QUEUED,
                    index_error=row.index_error,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return recent_docs_map

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
                accessible_knowledge_base_condition(self.user_id),
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
        """Delete a knowledge base together with its documents."""
        knowledge_base = await self.get_by_id(knowledge_base_id)
        if not knowledge_base:
            return False
        await self.db.execute(
            delete(Document).where(
                Document.knowledge_base_id == knowledge_base_id,
            )
        )
        await self.db.delete(knowledge_base)
        await self.db.commit()
        return True
