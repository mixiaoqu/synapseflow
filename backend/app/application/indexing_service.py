"""Application service for asynchronous document indexing orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from fastapi import BackgroundTasks, HTTPException
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, KnowledgeBase
from app.db.session import AsyncSessionLocal
from app.repositories.document_repository import DocumentRepository
from app.services.document_index_state import (
    ACTIVE_INDEX_STATUSES,
    INDEX_STATUS_FAILED,
    INDEX_STATUS_INDEXED,
    INDEX_STATUS_PROCESSING,
    INDEX_STATUS_QUEUED,
)
from app.services.document_indexer import index_document
from app.services.vector_store import delete_by_document_id

MAX_INDEX_ERROR_LENGTH = 1000


class IndexingService:
    """Owns index queueing, background execution, and explicit document states."""

    @staticmethod
    def _truncate_error(error: Exception) -> str:
        return str(error).strip()[:MAX_INDEX_ERROR_LENGTH] or error.__class__.__name__

    @staticmethod
    async def _get_document(db: AsyncSession, document_id: int) -> Document | None:
        result = await db.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_document_hash(
        db: AsyncSession,
        document_id: int,
    ) -> str | None:
        result = await db.execute(
            select(Document.content_hash).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    def enqueue_document(
        self,
        background_tasks: BackgroundTasks,
        *,
        document_id: int,
        expected_content_hash: str,
    ) -> None:
        """Queue one document indexing task."""
        background_tasks.add_task(
            self.index_document_task,
            document_id=document_id,
            expected_content_hash=expected_content_hash,
        )

    def enqueue_documents_batch(
        self,
        background_tasks: BackgroundTasks,
        *,
        documents: Sequence[tuple[int, str]],
    ) -> None:
        """Queue multiple document indexing tasks."""
        if not documents:
            return
        background_tasks.add_task(
            self.index_documents_batch_task,
            documents=list(documents),
        )

    def enqueue_current_document_reindex(
        self,
        background_tasks: BackgroundTasks,
        *,
        target_document_id: int,
        target_content_hash: str,
        previous_document_id: int | None = None,
    ) -> None:
        """Queue a current-version switch/index task."""
        background_tasks.add_task(
            self.reindex_current_document_task,
            target_document_id=target_document_id,
            target_content_hash=target_content_hash,
            previous_document_id=previous_document_id,
        )

    async def _mark_processing(
        self,
        db: AsyncSession,
        *,
        document_id: int,
        expected_content_hash: str,
    ) -> bool:
        result = await db.execute(
            update(Document)
            .where(
                Document.id == document_id,
                Document.content_hash == expected_content_hash,
            )
            .values(
                index_status=INDEX_STATUS_PROCESSING,
                index_error=None,
            )
        )
        if not result.rowcount:
            await db.rollback()
            return False
        await db.commit()
        return True

    async def _mark_failed(
        self,
        db: AsyncSession,
        *,
        document_id: int,
        expected_content_hash: str,
        error_message: str,
    ) -> None:
        await db.execute(
            update(Document)
            .where(
                Document.id == document_id,
                Document.content_hash == expected_content_hash,
            )
            .values(
                index_status=INDEX_STATUS_FAILED,
                index_error=error_message,
                indexed_at=None,
            )
        )
        await db.commit()

    async def _run_document_index(
        self,
        db: AsyncSession,
        *,
        document_id: int,
        expected_content_hash: str,
    ) -> int | None:
        doc = await self._get_document(db, document_id)
        if not doc:
            logger.warning(
                "Skipped document indexing because doc_id={} was not found",
                document_id,
            )
            return None

        if doc.content_hash != expected_content_hash:
            logger.info(
                "Skipped stale indexing task doc_id={} expected_hash={} actual_hash={}",
                document_id,
                expected_content_hash,
                doc.content_hash,
            )
            return None

        if not await self._mark_processing(
            db,
            document_id=document_id,
            expected_content_hash=expected_content_hash,
        ):
            logger.info(
                "Skipped document indexing because doc_id={} no longer matches queued hash",
                document_id,
            )
            return None

        doc = await self._get_document(db, document_id)
        if not doc or doc.content_hash != expected_content_hash:
            logger.info("Skipped document indexing after refresh because doc_id={} changed", document_id)
            return None

        try:
            count = await index_document(
                db,
                doc.id,
                doc.content or "",
                doc.title,
                commit=False,
            )
            current_hash = await self._get_document_hash(db, doc.id)
            if current_hash != expected_content_hash:
                await db.rollback()
                logger.info(
                    "Discarded stale indexing result doc_id={} expected_hash={} actual_hash={}",
                    doc.id,
                    expected_content_hash,
                    current_hash,
                )
                return None

            await db.execute(
                update(Document)
                .where(
                    Document.id == doc.id,
                    Document.content_hash == expected_content_hash,
                )
                .values(
                    index_status=INDEX_STATUS_INDEXED,
                    index_error=None,
                    indexed_at=datetime.utcnow(),
                )
            )
            await db.commit()
            logger.info("Indexed document doc_id={} chunks={}", doc.id, count)
            return count
        except Exception as exc:
            await db.rollback()
            await self._mark_failed(
                db,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                error_message=self._truncate_error(exc),
            )
            logger.warning("Document indexing failed doc_id={}: {}", document_id, exc)
            return None

    async def index_document_task(
        self,
        *,
        document_id: int,
        expected_content_hash: str,
    ) -> None:
        """Background entrypoint for one document."""
        async with AsyncSessionLocal() as db:
            await self._run_document_index(
                db,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
            )

    async def index_documents_batch_task(
        self,
        *,
        documents: Sequence[tuple[int, str]],
    ) -> None:
        """Background entrypoint for multiple documents."""
        for document_id, expected_content_hash in documents:
            await self.index_document_task(
                document_id=document_id,
                expected_content_hash=expected_content_hash,
            )

    async def reindex_current_document_task(
        self,
        *,
        target_document_id: int,
        target_content_hash: str,
        previous_document_id: int | None = None,
    ) -> None:
        """Background entrypoint for current-version switches and new versions."""
        async with AsyncSessionLocal() as db:
            try:
                if previous_document_id and previous_document_id != target_document_id:
                    await db.execute(
                        update(Document)
                        .where(Document.id == previous_document_id)
                        .values(
                            index_status=INDEX_STATUS_QUEUED,
                            index_error=None,
                            indexed_at=None,
                        )
                    )
                    await delete_by_document_id(db, previous_document_id, commit=False)
                    await db.commit()
                await self._run_document_index(
                    db,
                    document_id=target_document_id,
                    expected_content_hash=target_content_hash,
                )
            except Exception as exc:
                await db.rollback()
                logger.warning(
                    "Current document reindex failed target_doc_id={}: {}",
                    target_document_id,
                    exc,
                )

    async def _list_reindex_targets(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        team_id: int | None = None,
        knowledge_base_id: int | None = None,
    ) -> list[Document]:
        stmt = select(Document).where(
            Document.is_current.is_(True),
            Document.user_id == user_id,
        )
        if knowledge_base_id is not None:
            stmt = stmt.where(Document.knowledge_base_id == knowledge_base_id)
        elif team_id is not None:
            stmt = stmt.join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id).where(
                KnowledgeBase.team_id == team_id,
            )
        stmt = stmt.order_by(Document.id.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def reindex_all_documents(
        self,
        *,
        background_tasks: BackgroundTasks,
        db: AsyncSession,
        user_id: int,
        team_id: int | None = None,
        knowledge_base_id: int | None = None,
    ) -> dict[str, int | str]:
        """Queue a full reindex instead of blocking the request."""
        docs = await self._list_reindex_targets(
            db=db,
            user_id=user_id,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        for doc in docs:
            doc.index_status = INDEX_STATUS_QUEUED
            doc.index_error = None
            doc.indexed_at = None
        await db.commit()
        for doc in docs:
            await db.refresh(doc)

        queued_docs = [(doc.id, doc.content_hash) for doc in docs]
        self.enqueue_documents_batch(background_tasks, documents=queued_docs)
        logger.info("Queued full reindex for {} documents", len(queued_docs))
        return {
            "message": f"Queued {len(queued_docs)} documents for reindexing",
            "queued": len(queued_docs),
        }

    async def index_single_document(
        self,
        *,
        background_tasks: BackgroundTasks,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> dict[str, int | str]:
        """Queue one document for asynchronous indexing."""
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.get_by_id_for_user(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc.index_status in ACTIVE_INDEX_STATUSES:
            return {
                "message": "Document is already queued for indexing",
                "queued": 0,
            }

        doc.index_status = INDEX_STATUS_QUEUED
        doc.index_error = None
        doc.indexed_at = None
        await db.commit()
        await db.refresh(doc)
        self.enqueue_document(
            background_tasks,
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
        )
        return {
            "message": "Document queued for indexing",
            "queued": 1,
        }


indexing_service = IndexingService()
