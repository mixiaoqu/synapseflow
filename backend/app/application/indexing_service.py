"""Application service for asynchronous document indexing orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, HTTPException
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.registry import config_registry
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
from app.services.document_indexer import (
    estimate_document_chunk_count,
    index_document,
    index_documents_batch,
)
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

    @staticmethod
    async def _get_document_hashes(
        db: AsyncSession,
        document_ids: Sequence[int],
    ) -> dict[int, str]:
        if not document_ids:
            return {}
        result = await db.execute(
            select(Document.id, Document.content_hash).where(Document.id.in_(document_ids))
        )
        return {int(doc_id): str(content_hash or "") for doc_id, content_hash in result.all()}

    @staticmethod
    async def _get_documents_for_ids(
        db: AsyncSession,
        document_ids: Sequence[int],
    ) -> dict[int, Document]:
        if not document_ids:
            return {}
        result = await db.execute(select(Document).where(Document.id.in_(document_ids)))
        return {int(doc.id): doc for doc in result.scalars().all()}

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

    def _build_dynamic_batches(
        self,
        documents: Sequence[dict[str, Any]],
    ) -> list[list[dict[str, Any]]]:
        """Group documents into conservative multi-document embedding batches."""
        batch_cfg = config_registry.get_indexing_batch_config()
        max_docs = batch_cfg.max_docs
        max_chunks = batch_cfg.max_chunks
        max_chars = batch_cfg.max_chars
        batches: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_chunks = 0
        current_chars = 0

        for document in documents:
            doc_chars = int(document["char_count"])
            doc_chunks = int(document["chunk_count"])
            exceeds_current_batch = (
                current
                and (
                    len(current) >= max_docs
                    or current_chunks + doc_chunks > max_chunks
                    or current_chars + doc_chars > max_chars
                )
            )
            if exceeds_current_batch:
                batches.append(current)
                current = []
                current_chunks = 0
                current_chars = 0

            current.append(document)
            current_chunks += doc_chunks
            current_chars += doc_chars

            # Very large documents become a batch of their own.
            if (
                doc_chunks >= max_chunks
                or doc_chars >= max_chars
                or len(current) >= max_docs
            ):
                batches.append(current)
                current = []
                current_chunks = 0
                current_chars = 0

        if current:
            batches.append(current)
        return batches

    async def _prepare_batch_candidates(
        self,
        db: AsyncSession,
        documents: Sequence[tuple[int, str]],
    ) -> list[dict[str, Any]]:
        document_ids = [document_id for document_id, _ in documents]
        docs_by_id = await self._get_documents_for_ids(db, document_ids)
        prepared: list[dict[str, Any]] = []

        for document_id, expected_content_hash in documents:
            doc = docs_by_id.get(document_id)
            if not doc:
                logger.warning(
                    "Skipped document indexing because doc_id={} was not found",
                    document_id,
                )
                continue

            if doc.content_hash != expected_content_hash:
                logger.info(
                    "Skipped stale indexing task doc_id={} expected_hash={} actual_hash={}",
                    document_id,
                    expected_content_hash,
                    doc.content_hash,
                )
                continue

            if not await self._mark_processing(
                db,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
            ):
                logger.info(
                    "Skipped document indexing because doc_id={} no longer matches queued hash",
                    document_id,
                )
                continue

            refreshed = await self._get_document(db, document_id)
            if not refreshed or refreshed.content_hash != expected_content_hash:
                logger.info(
                    "Skipped document indexing after refresh because doc_id={} changed",
                    document_id,
                )
                continue

            content = refreshed.content or ""
            title = refreshed.title
            prepared.append(
                {
                    "document_id": refreshed.id,
                    "expected_content_hash": expected_content_hash,
                    "content": content,
                    "title": title,
                    "char_count": len(content),
                    "chunk_count": estimate_document_chunk_count(content, title),
                }
            )

        return prepared

    async def _run_document_batch_index(
        self,
        db: AsyncSession,
        *,
        batch: Sequence[dict[str, Any]],
    ) -> dict[int, int]:
        raw_documents = [
            (int(item["document_id"]), str(item["content"]), item.get("title"))
            for item in batch
        ]
        counts = await index_documents_batch(db, raw_documents, commit=False)
        current_hashes = await self._get_document_hashes(
            db,
            [int(item["document_id"]) for item in batch],
        )
        indexed_at = datetime.utcnow()
        finalized_counts: dict[int, int] = {}

        for item in batch:
            document_id = int(item["document_id"])
            expected_content_hash = str(item["expected_content_hash"])
            current_hash = current_hashes.get(document_id)
            if current_hash != expected_content_hash:
                await delete_by_document_id(db, document_id, commit=False)
                logger.info(
                    "Discarded stale batched indexing result doc_id={} expected_hash={} actual_hash={}",
                    document_id,
                    expected_content_hash,
                    current_hash,
                )
                continue

            await db.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.content_hash == expected_content_hash,
                )
                .values(
                    index_status=INDEX_STATUS_INDEXED,
                    index_error=None,
                    indexed_at=indexed_at,
                )
            )
            finalized_counts[document_id] = counts.get(document_id, 0)

        await db.commit()
        return finalized_counts

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
        async with AsyncSessionLocal() as db:
            prepared = await self._prepare_batch_candidates(db, documents)
            batches = self._build_dynamic_batches(prepared)

            for batch in batches:
                try:
                    counts = await self._run_document_batch_index(db, batch=batch)
                    total_chunks = sum(counts.values())
                    logger.info(
                        "Indexed batch docs={} chunks={}",
                        len(counts),
                        total_chunks,
                    )
                except Exception as exc:
                    await db.rollback()
                    logger.warning(
                        "Batch indexing failed docs={} error={} | falling back to per-document indexing",
                        len(batch),
                        exc,
                    )
                    for item in batch:
                        await self._run_document_index(
                            db,
                            document_id=int(item["document_id"]),
                            expected_content_hash=str(item["expected_content_hash"]),
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
