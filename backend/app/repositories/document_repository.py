"""Document repository helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentCategory, KnowledgeBase
from app.services.document_index_state import (
    INDEX_STATUS_FAILED,
    INDEX_STATUS_INDEXED,
    INDEX_STATUS_PROCESSING,
    INDEX_STATUS_QUEUED,
    compute_content_hash,
)


@dataclass(slots=True)
class DocumentIndexingStatusCounts:
    queued: int
    processing: int
    indexed: int
    failed: int
    total: int


@dataclass(slots=True)
class RecentFailedDocumentRecord:
    document_id: int
    title: str
    knowledge_base_id: int | None
    knowledge_base_name: str | None
    index_error: str | None
    updated_at: datetime


@dataclass(slots=True)
class ActiveIndexingScopeRecord:
    knowledge_base_id: int | None
    knowledge_base_name: str
    queued: int
    processing: int
    indexed: int
    failed: int
    total: int
    updated_at: datetime | None


class DocumentRepository:
    """Encapsulates document persistence operations."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def create(
        self,
        *,
        title: str,
        content: str,
        document_type: str | None = None,
        size: int = 0,
        knowledge_base_id: int | None = None,
        category_id: int | None = None,
        source_path: str | None = None,
        commit: bool = True,
    ) -> Document:
        """Create a document row and set its root_id in the same transaction."""
        doc = Document(
            user_id=self.user_id,
            title=title,
            content=content,
            document_type=document_type,
            size=size,
            content_hash=compute_content_hash(content),
            index_status=INDEX_STATUS_QUEUED,
            index_error=None,
            indexed_at=None,
            version=1,
            parent_id=None,
            is_latest=True,
            is_current=True,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            source_path=source_path,
        )
        self.db.add(doc)
        await self.db.flush()
        doc.root_id = doc.id
        if commit:
            await self.db.commit()
            await self.db.refresh(doc)
        return doc

    async def add_for_batch(self, doc: Document) -> None:
        """Queue a document row for batch creation."""
        self.db.add(doc)

    async def prepare_batch_create(self, docs: list[Document]) -> None:
        """Flush ids and assign root_ids without committing yet."""
        if not docs:
            return
        await self.db.flush()
        for doc in docs:
            doc.root_id = doc.id

    async def commit_and_refresh_root_ids(self, docs: list[Document]) -> None:
        """Flush ids, set root_ids, and commit batch-created documents once."""
        await self.prepare_batch_create(docs)
        await self.db.commit()
        for doc in docs:
            await self.db.refresh(doc)

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        team_id: int | None = None,
        knowledge_base_id: int | None = None,
        category_id: int | None = None,
    ) -> tuple[list[tuple[Document, str | None, str | None]], int]:
        """Return paginated current documents plus knowledge-base/category names."""
        base_filter = Document.user_id == self.user_id
        base_filter = base_filter & Document.is_current.is_(True)
        if keyword and keyword.strip():
            base_filter = base_filter & Document.title.ilike(f"%{keyword.strip()}%")
        if knowledge_base_id is not None:
            if knowledge_base_id == 0:
                base_filter = base_filter & Document.knowledge_base_id.is_(None)
            else:
                base_filter = base_filter & (Document.knowledge_base_id == knowledge_base_id)
        if category_id is not None:
            if category_id == 0:
                base_filter = base_filter & Document.category_id.is_(None)
            else:
                base_filter = base_filter & (Document.category_id == category_id)

        count_query = (
            select(func.count())
            .select_from(Document)
            .outerjoin(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(DocumentCategory, Document.category_id == DocumentCategory.id)
            .where(base_filter)
        )
        if team_id is not None:
            count_query = count_query.where(
                and_(
                    Document.knowledge_base_id.is_not(None),
                    KnowledgeBase.team_id == team_id,
                )
            )
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(
                Document,
                KnowledgeBase.name.label("knowledge_base_name"),
                DocumentCategory.name.label("category_name"),
            )
            .outerjoin(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(DocumentCategory, Document.category_id == DocumentCategory.id)
            .where(base_filter)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        if team_id is not None:
            stmt = stmt.where(
                and_(
                    Document.knowledge_base_id.is_not(None),
                    KnowledgeBase.team_id == team_id,
                )
            )
        result = await self.db.execute(stmt)
        return list(result.all()), total

    async def get_category_name(self, category_id: int | None) -> str | None:
        """Fetch a category name scoped to the current user."""
        if category_id is None:
            return None
        result = await self.db.execute(
            select(DocumentCategory.name)
            .join(KnowledgeBase, KnowledgeBase.id == DocumentCategory.knowledge_base_id)
            .where(
                DocumentCategory.id == category_id,
                KnowledgeBase.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, doc_id: int) -> Document | None:
        """Fetch a document by id without user filtering."""
        result = await self.db.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, doc_id: int) -> Document | None:
        """Fetch a document by id scoped to the current user."""
        result = await self.db.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_versions_by_doc_id(self, doc_id: int) -> list[Document]:
        """Return the version chain for a document."""
        doc = await self.get_by_id(doc_id)
        if not doc:
            return []
        root_id = getattr(doc, "root_id", None) or doc.id
        stmt = (
            select(Document)
            .where(Document.root_id == root_id, Document.user_id == self.user_id)
            .order_by(Document.version.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_content(self, doc_id: int, content: str) -> Document | None:
        """Replace the content of an existing latest document."""
        doc = await self.get_by_id_for_user(doc_id)
        if not doc:
            return None
        doc.content = content
        doc.size = len(content.encode("utf-8"))
        doc.content_hash = compute_content_hash(content)
        doc.index_status = INDEX_STATUS_QUEUED
        doc.index_error = None
        doc.indexed_at = None
        doc.version = (doc.version or 1) + 1
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def get_current_by_root_id(self, root_id: int) -> Document | None:
        """Fetch the current version for a version chain."""
        result = await self.db.execute(
            select(Document)
            .where(
                Document.root_id == root_id,
                Document.user_id == self.user_id,
                Document.is_current.is_(True),
            )
            .order_by(
                Document.is_latest.desc(),
                Document.version.desc(),
                Document.updated_at.desc(),
                Document.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def clear_current_flags_for_root_id(self, root_id: int) -> None:
        """Clear current flags for every version in a chain."""
        await self.db.execute(
            update(Document)
            .where(
                Document.root_id == root_id,
                Document.user_id == self.user_id,
                Document.is_current.is_(True),
            )
            .values(is_current=False)
        )

    async def get_latest_by_root_id(self, root_id: int) -> Document | None:
        """Fetch the latest version for a version chain."""
        result = await self.db.execute(
            select(Document).where(
                Document.root_id == root_id,
                Document.user_id == self.user_id,
                Document.is_latest.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def create_version(
        self,
        doc_id: int,
        content: str,
        *,
        commit: bool = True,
    ) -> Document | None:
        """Create a new latest version row for a document."""
        orig = await self.get_by_id_for_user(doc_id)
        if not orig:
            return None
        root_id = orig.root_id or orig.id
        latest_doc = await self.get_latest_by_root_id(root_id)
        current_doc = await self.get_current_by_root_id(root_id)
        max_version = getattr(latest_doc, "version", None)
        new_doc = Document(
            user_id=self.user_id,
            title=(latest_doc.title if latest_doc else orig.title),
            content=content,
            document_type=(latest_doc.document_type if latest_doc else orig.document_type),
            size=len(content.encode("utf-8")),
            content_hash=compute_content_hash(content),
            index_status=INDEX_STATUS_QUEUED,
            index_error=None,
            indexed_at=None,
            version=(max_version or 1) + 1,
            parent_id=(latest_doc.id if latest_doc else orig.id),
            root_id=root_id,
            is_latest=True,
            is_current=True,
            knowledge_base_id=getattr(latest_doc or orig, "knowledge_base_id", None),
            category_id=getattr(latest_doc or orig, "category_id", None),
            source_path=getattr(latest_doc or orig, "source_path", None),
        )
        if latest_doc:
            latest_doc.is_latest = False
        await self.clear_current_flags_for_root_id(root_id)
        self.db.add(new_doc)
        if commit:
            await self.db.commit()
            await self.db.refresh(new_doc)
        else:
            await self.db.flush()
        return new_doc

    async def switch_current_version(
        self,
        doc_id: int,
        *,
        commit: bool = True,
    ) -> tuple[Document | None, Document | None]:
        """Switch the current version within a document chain."""
        target = await self.get_by_id_for_user(doc_id)
        if not target:
            return None, None

        root_id = target.root_id or target.id
        current_doc = await self.get_current_by_root_id(root_id)
        if current_doc and current_doc.id == target.id:
            return target, current_doc

        await self.clear_current_flags_for_root_id(root_id)
        target.is_current = True
        target.index_status = INDEX_STATUS_QUEUED
        target.index_error = None
        target.indexed_at = None

        if commit:
            await self.db.commit()
            await self.db.refresh(target)
            if current_doc:
                await self.db.refresh(current_doc)
        else:
            await self.db.flush()

        return target, current_doc

    async def get_by_ids(self, ids: list[int]) -> list[Document]:
        """Fetch multiple documents scoped to the current user."""
        if not ids:
            return []
        result = await self.db.execute(
            select(Document).where(
                Document.id.in_(ids),
                Document.user_id == self.user_id,
            )
        )
        return list(result.scalars().all())

    async def get_chain_by_root_ids(self, root_ids: set[int]) -> list[Document]:
        """Fetch all versions for each root id."""
        if not root_ids:
            return []
        result = await self.db.execute(
            select(Document).where(
                Document.root_id.in_(root_ids),
                Document.user_id == self.user_id,
            )
        )
        return list(result.scalars().all())

    async def delete_chain(self, docs: list[Document]) -> int:
        """Delete a full version chain."""
        for doc in docs:
            await self.db.delete(doc)
        await self.db.commit()
        return len(docs)

    async def count_total(self) -> int:
        """Count all documents in the table."""
        result = await self.db.execute(select(func.count()).select_from(Document))
        return result.scalar() or 0

    async def get_indexing_status_counts(self) -> DocumentIndexingStatusCounts:
        """Return aggregated indexing status counters for current documents."""
        indexed_count = func.sum(case((Document.index_status == INDEX_STATUS_INDEXED, 1), else_=0))
        queued_count = func.sum(case((Document.index_status == INDEX_STATUS_QUEUED, 1), else_=0))
        processing_count = func.sum(
            case((Document.index_status == INDEX_STATUS_PROCESSING, 1), else_=0)
        )
        failed_count = func.sum(case((Document.index_status == INDEX_STATUS_FAILED, 1), else_=0))
        result = await self.db.execute(
            select(
                func.count(Document.id).label("total"),
                indexed_count.label("indexed"),
                queued_count.label("queued"),
                processing_count.label("processing"),
                failed_count.label("failed"),
            ).where(
                Document.user_id == self.user_id,
                Document.is_current.is_(True),
            )
        )
        row = result.one()
        return DocumentIndexingStatusCounts(
            queued=row.queued or 0,
            processing=row.processing or 0,
            indexed=row.indexed or 0,
            failed=row.failed or 0,
            total=row.total or 0,
        )

    async def list_recent_failed_documents(
        self,
        *,
        limit: int = 5,
    ) -> list[RecentFailedDocumentRecord]:
        """Return recent failed current documents for the task panel."""
        stmt = (
            select(
                Document.id.label("document_id"),
                Document.title.label("title"),
                Document.knowledge_base_id.label("knowledge_base_id"),
                KnowledgeBase.name.label("knowledge_base_name"),
                Document.index_error.label("index_error"),
                Document.updated_at.label("updated_at"),
            )
            .outerjoin(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(
                Document.user_id == self.user_id,
                Document.is_current.is_(True),
                Document.index_status == INDEX_STATUS_FAILED,
            )
            .order_by(Document.updated_at.desc(), Document.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            RecentFailedDocumentRecord(
                document_id=row.document_id,
                title=row.title,
                knowledge_base_id=row.knowledge_base_id,
                knowledge_base_name=row.knowledge_base_name,
                index_error=row.index_error,
                updated_at=row.updated_at,
            )
            for row in result
        ]

    async def list_active_indexing_scopes(self) -> list[ActiveIndexingScopeRecord]:
        """Return current-task progress grouped by knowledge base.

        The "current task" boundary is inferred from the earliest queued/processing
        document update within each active knowledge base. Documents updated after
        that timestamp are treated as part of the same indexing wave.
        """
        active_start_stmt = (
            select(
                Document.knowledge_base_id.label("knowledge_base_id"),
                KnowledgeBase.name.label("knowledge_base_name"),
                func.min(Document.updated_at).label("started_at"),
            )
            .outerjoin(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(
                Document.user_id == self.user_id,
                Document.is_current.is_(True),
                Document.index_status.in_((INDEX_STATUS_QUEUED, INDEX_STATUS_PROCESSING)),
            )
            .group_by(Document.knowledge_base_id, KnowledgeBase.name)
        )
        active_rows = (await self.db.execute(active_start_stmt)).all()
        if not active_rows:
            return []

        starts_by_kb: dict[int | None, tuple[str, datetime]] = {}
        knowledge_base_ids: list[int] = []
        for row in active_rows:
            if row.started_at is None:
                continue
            starts_by_kb[row.knowledge_base_id] = (
                row.knowledge_base_name or "未归档文档",
                row.started_at,
            )
            if row.knowledge_base_id is not None:
                knowledge_base_ids.append(row.knowledge_base_id)

        filters = [Document.knowledge_base_id.in_(knowledge_base_ids)] if knowledge_base_ids else []
        if None in starts_by_kb:
            filters.append(Document.knowledge_base_id.is_(None))

        if not filters:
            return []

        docs_stmt = (
            select(
                Document.knowledge_base_id.label("knowledge_base_id"),
                KnowledgeBase.name.label("knowledge_base_name"),
                Document.index_status.label("index_status"),
                Document.updated_at.label("updated_at"),
                Document.indexed_at.label("indexed_at"),
            )
            .outerjoin(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(
                Document.user_id == self.user_id,
                Document.is_current.is_(True),
                or_(*filters),
            )
        )
        rows = (await self.db.execute(docs_stmt)).all()

        buckets: dict[int | None, ActiveIndexingScopeRecord] = {}
        for row in rows:
            kb_id = row.knowledge_base_id
            if kb_id not in starts_by_kb:
                continue
            kb_name, started_at = starts_by_kb[kb_id]
            updated_at = row.updated_at
            indexed_at = row.indexed_at
            qualifies = False
            if updated_at and updated_at >= started_at:
                qualifies = True
            if indexed_at and indexed_at >= started_at:
                qualifies = True
            if not qualifies:
                continue

            record = buckets.get(kb_id)
            if record is None:
                record = ActiveIndexingScopeRecord(
                    knowledge_base_id=kb_id,
                    knowledge_base_name=row.knowledge_base_name or kb_name,
                    queued=0,
                    processing=0,
                    indexed=0,
                    failed=0,
                    total=0,
                    updated_at=started_at,
                )
                buckets[kb_id] = record

            status = row.index_status or INDEX_STATUS_QUEUED
            if status == INDEX_STATUS_QUEUED:
                record.queued += 1
            elif status == INDEX_STATUS_PROCESSING:
                record.processing += 1
            elif status == INDEX_STATUS_INDEXED:
                record.indexed += 1
            elif status == INDEX_STATUS_FAILED:
                record.failed += 1

            record.total += 1
            latest_point = indexed_at or updated_at
            if latest_point and (record.updated_at is None or latest_point > record.updated_at):
                record.updated_at = latest_point

        return sorted(
            buckets.values(),
            key=lambda item: (
                item.processing,
                item.queued,
                item.updated_at.timestamp() if item.updated_at else 0.0,
            ),
            reverse=True,
        )
