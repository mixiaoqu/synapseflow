"""Application service for asynchronous document indexing orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from importlib import import_module
from typing import Any

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.registry import config_registry
from app.db.models import Document, KnowledgeBase
from app.db.session import AsyncSessionLocal
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.index_job_repository import IndexJobRepository
from app.services.document_index_state import (
    ACTIVE_INDEX_STATUSES,
    INDEX_STATUS_FAILED,
    INDEX_STATUS_INDEXED,
    INDEX_STATUS_PROCESSING,
    INDEX_STATUS_QUEUED,
)
from app.services.document_indexer import (
    index_document,
    index_prepared_documents_batch,
)
from app.services.index_job_state import (
    INDEX_JOB_DOCUMENT_STATUS_FAILED,
    INDEX_JOB_DOCUMENT_STATUS_INDEXED,
    INDEX_JOB_DOCUMENT_STATUS_PROCESSING,
)
from app.services.vector_store import delete_by_document_id
from app.utils.time import utc_now

MAX_INDEX_ERROR_LENGTH = 1000
MAX_INDEX_MESSAGE_DOCUMENTS = 20


class IndexingService:
    """Owns index queueing, background execution, and explicit document states."""

    @staticmethod
    def _actor_module():
        return import_module("app.workers.indexing_tasks")

    @staticmethod
    def _serialize_documents(documents: Sequence[tuple[int, str]]) -> list[dict[str, Any]]:
        return [
            {
                "document_id": int(document_id),
                "expected_content_hash": str(expected_content_hash),
            }
            for document_id, expected_content_hash in documents
        ]

    @staticmethod
    def _chunk_document_messages(
        documents: Sequence[tuple[int, str]],
        *,
        size: int = MAX_INDEX_MESSAGE_DOCUMENTS,
    ) -> list[list[tuple[int, str]]]:
        chunk_size = max(1, size)
        return [
            list(documents[start : start + chunk_size])
            for start in range(0, len(documents), chunk_size)
        ]

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

    async def _create_job(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        documents: Sequence[tuple[int, str]],
        title: str,
        job_type: str,
        knowledge_base_id: int | None,
    ) -> int:
        repo = IndexJobRepository(db)
        job = await repo.create_job(
            user_id=user_id,
            title=title,
            job_type=job_type,
            knowledge_base_id=knowledge_base_id,
            documents=list(documents),
        )
        return job.id

    @staticmethod
    async def _mark_documents_dispatch_failed(
        db: AsyncSession,
        *,
        documents: Sequence[tuple[int, str]],
        error_message: str,
    ) -> None:
        for document_id, expected_content_hash in documents:
            await db.execute(
                update(Document)
                .where(
                    Document.id == int(document_id),
                    Document.content_hash == str(expected_content_hash),
                )
                .values(
                    index_status=INDEX_STATUS_FAILED,
                    index_error=error_message,
                    indexed_at=None,
                )
            )
        await db.commit()

    async def enqueue_document_job(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        document_id: int,
        expected_content_hash: str,
        knowledge_base_id: int | None,
        title: str,
        job_type: str = "index_document",
    ) -> int:
        job_id = await self._create_job(
            db,
            user_id=user_id,
            documents=[(document_id, expected_content_hash)],
            title=title,
            job_type=job_type,
            knowledge_base_id=knowledge_base_id,
        )
        try:
            self.enqueue_document(
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                job_id=job_id,
            )
        except Exception as exc:
            error_message = self._truncate_error(exc)
            await self._mark_documents_dispatch_failed(
                db,
                documents=[(document_id, expected_content_hash)],
                error_message=error_message,
            )
            await IndexJobRepository(db).mark_job_dispatch_failed(
                job_id=job_id,
                error_message=error_message,
            )
            raise
        return job_id

    async def enqueue_documents_batch_job(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        documents: Sequence[tuple[int, str]],
        knowledge_base_id: int | None,
        title: str,
        job_type: str = "index_documents_batch",
    ) -> int | None:
        if not documents:
            return None
        job_id = await self._create_job(
            db,
            user_id=user_id,
            documents=documents,
            title=title,
            job_type=job_type,
            knowledge_base_id=knowledge_base_id,
        )
        try:
            self.enqueue_documents_batch(documents=documents, job_id=job_id)
        except Exception as exc:
            error_message = self._truncate_error(exc)
            await self._mark_documents_dispatch_failed(
                db,
                documents=documents,
                error_message=error_message,
            )
            await IndexJobRepository(db).mark_job_dispatch_failed(
                job_id=job_id,
                error_message=error_message,
            )
            raise
        return job_id

    async def enqueue_current_document_reindex_job(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        target_document_id: int,
        target_content_hash: str,
        knowledge_base_id: int | None,
        title: str,
        previous_document_id: int | None = None,
        job_type: str = "reindex_current_document",
    ) -> int:
        job_id = await self._create_job(
            db,
            user_id=user_id,
            documents=[(target_document_id, target_content_hash)],
            title=title,
            job_type=job_type,
            knowledge_base_id=knowledge_base_id,
        )
        try:
            self.enqueue_current_document_reindex(
                target_document_id=target_document_id,
                target_content_hash=target_content_hash,
                previous_document_id=previous_document_id,
                job_id=job_id,
            )
        except Exception as exc:
            error_message = self._truncate_error(exc)
            await self._mark_documents_dispatch_failed(
                db,
                documents=[(target_document_id, target_content_hash)],
                error_message=error_message,
            )
            await IndexJobRepository(db).mark_job_dispatch_failed(
                job_id=job_id,
                error_message=error_message,
            )
            raise
        return job_id

    def enqueue_document(
        self,
        *,
        document_id: int,
        expected_content_hash: str,
        job_id: int,
    ) -> None:
        """Queue one document indexing task."""
        actor_module = self._actor_module()
        actor_module.index_document_actor.send(
            document_id=document_id,
            expected_content_hash=expected_content_hash,
            job_id=job_id,
        )

    def enqueue_documents_batch(
        self,
        *,
        documents: Sequence[tuple[int, str]],
        job_id: int,
    ) -> None:
        """Queue multiple document indexing tasks."""
        if not documents:
            return
        actor_module = self._actor_module()
        for chunk in self._chunk_document_messages(documents):
            actor_module.index_documents_batch_actor.send(
                documents=self._serialize_documents(chunk),
                job_id=job_id,
            )

    def enqueue_current_document_reindex(
        self,
        *,
        target_document_id: int,
        target_content_hash: str,
        job_id: int,
        previous_document_id: int | None = None,
    ) -> None:
        """Queue a current-version switch/index task."""
        actor_module = self._actor_module()
        actor_module.reindex_current_document_actor.send(
            target_document_id=target_document_id,
            target_content_hash=target_content_hash,
            previous_document_id=previous_document_id,
            job_id=job_id,
        )

    async def _set_job_document_status(
        self,
        db: AsyncSession,
        *,
        job_id: int | None,
        document_id: int,
        expected_content_hash: str,
        status: str,
        error_message: str | None = None,
        indexed_at: datetime | None = None,
    ) -> None:
        if job_id is None:
            return
        await IndexJobRepository(db).set_document_status(
            job_id=job_id,
            document_id=document_id,
            expected_content_hash=expected_content_hash,
            status=status,
            error_message=error_message,
            indexed_at=indexed_at,
        )

    async def _mark_job_document_failed(
        self,
        db: AsyncSession,
        *,
        job_id: int | None,
        document_id: int,
        expected_content_hash: str,
        error_message: str,
    ) -> None:
        await self._set_job_document_status(
            db,
            job_id=job_id,
            document_id=document_id,
            expected_content_hash=expected_content_hash,
            status=INDEX_JOB_DOCUMENT_STATUS_FAILED,
            error_message=error_message,
            indexed_at=None,
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
        job_id: int | None = None,
    ) -> int | None:
        doc = await self._get_document(db, document_id)
        if not doc:
            await self._mark_job_document_failed(
                db,
                job_id=job_id,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                error_message="文档不存在，任务已跳过",
            )
            logger.warning(
                "Skipped document indexing because doc_id={} was not found",
                document_id,
            )
            return None

        if doc.content_hash != expected_content_hash:
            await self._mark_job_document_failed(
                db,
                job_id=job_id,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                error_message="文档内容已变化，旧任务已跳过",
            )
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
            await self._mark_job_document_failed(
                db,
                job_id=job_id,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                error_message="文档内容已变化，旧任务已跳过",
            )
            logger.info(
                "Skipped document indexing because doc_id={} no longer matches queued hash",
                document_id,
            )
            return None

        await self._set_job_document_status(
            db,
            job_id=job_id,
            document_id=document_id,
            expected_content_hash=expected_content_hash,
            status=INDEX_JOB_DOCUMENT_STATUS_PROCESSING,
        )

        doc = await self._get_document(db, document_id)
        if not doc or doc.content_hash != expected_content_hash:
            await self._mark_job_document_failed(
                db,
                job_id=job_id,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                error_message="文档内容已变化，旧任务已跳过",
            )
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
                await self._mark_job_document_failed(
                    db,
                    job_id=job_id,
                    document_id=doc.id,
                    expected_content_hash=expected_content_hash,
                    error_message="文档内容已变化，索引结果已丢弃",
                )
                logger.info(
                    "Discarded stale indexing result doc_id={} expected_hash={} actual_hash={}",
                    doc.id,
                    expected_content_hash,
                    current_hash,
                )
                return None

            indexed_at = utc_now()
            await db.execute(
                update(Document)
                .where(
                    Document.id == doc.id,
                    Document.content_hash == expected_content_hash,
                )
                .values(
                    index_status=INDEX_STATUS_INDEXED,
                    index_error=None,
                    indexed_at=indexed_at,
                )
            )
            await db.commit()
            await self._set_job_document_status(
                db,
                job_id=job_id,
                document_id=doc.id,
                expected_content_hash=expected_content_hash,
                status=INDEX_JOB_DOCUMENT_STATUS_INDEXED,
                indexed_at=indexed_at,
            )
            logger.info("Indexed document doc_id={} chunks={}", doc.id, count)
            return count
        except Exception as exc:
            await db.rollback()
            error_message = self._truncate_error(exc)
            await self._mark_failed(
                db,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                error_message=error_message,
            )
            await self._mark_job_document_failed(
                db,
                job_id=job_id,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                error_message=error_message,
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
        *,
        job_id: int | None = None,
    ) -> list[dict[str, Any]]:
        document_ids = [document_id for document_id, _ in documents]
        docs_by_id = await self._get_documents_for_ids(db, document_ids)
        job_statuses = (
            await IndexJobRepository(db).get_document_statuses(
                job_id=job_id,
                documents=list(documents),
            )
            if job_id is not None
            else {}
        )
        prepared: list[dict[str, Any]] = []
        chunk_repo = DocumentChunkRepository(db)

        for document_id, expected_content_hash in documents:
            job_document_status = job_statuses.get((document_id, expected_content_hash))
            if job_document_status in {
                INDEX_JOB_DOCUMENT_STATUS_INDEXED,
                INDEX_JOB_DOCUMENT_STATUS_FAILED,
            }:
                logger.info(
                    "Skipped terminal indexing job document job_id={} doc_id={} status={}",
                    job_id,
                    document_id,
                    job_document_status,
                )
                continue

            doc = docs_by_id.get(document_id)
            if not doc:
                await self._mark_job_document_failed(
                    db,
                    job_id=job_id,
                    document_id=document_id,
                    expected_content_hash=expected_content_hash,
                    error_message="文档不存在，任务已跳过",
                )
                logger.warning(
                    "Skipped document indexing because doc_id={} was not found",
                    document_id,
                )
                continue

            if doc.content_hash != expected_content_hash:
                await self._mark_job_document_failed(
                    db,
                    job_id=job_id,
                    document_id=document_id,
                    expected_content_hash=expected_content_hash,
                    error_message="文档内容已变化，旧任务已跳过",
                )
                logger.info(
                    "Skipped stale indexing task doc_id={} expected_hash={} actual_hash={}",
                    document_id,
                    expected_content_hash,
                    doc.content_hash,
                )
                continue

            if getattr(doc, "index_status", None) == INDEX_STATUS_INDEXED:
                indexed_at = getattr(doc, "indexed_at", None) or utc_now()
                await self._set_job_document_status(
                    db,
                    job_id=job_id,
                    document_id=document_id,
                    expected_content_hash=expected_content_hash,
                    status=INDEX_JOB_DOCUMENT_STATUS_INDEXED,
                    indexed_at=indexed_at,
                )
                logger.info(
                    "Skipped already indexed document during batch retry job_id={} doc_id={}",
                    job_id,
                    document_id,
                )
                continue

            if not await self._mark_processing(
                db,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
            ):
                await self._mark_job_document_failed(
                    db,
                    job_id=job_id,
                    document_id=document_id,
                    expected_content_hash=expected_content_hash,
                    error_message="文档内容已变化，旧任务已跳过",
                )
                logger.info(
                    "Skipped document indexing because doc_id={} no longer matches queued hash",
                    document_id,
                )
                continue

            await self._set_job_document_status(
                db,
                job_id=job_id,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                status=INDEX_JOB_DOCUMENT_STATUS_PROCESSING,
            )

            refreshed = await self._get_document(db, document_id)
            if not refreshed or refreshed.content_hash != expected_content_hash:
                await self._mark_job_document_failed(
                    db,
                    job_id=job_id,
                    document_id=document_id,
                    expected_content_hash=expected_content_hash,
                    error_message="文档内容已变化，旧任务已跳过",
                )
                logger.info(
                    "Skipped document indexing after refresh because doc_id={} changed",
                    document_id,
                )
                continue

            content = refreshed.content or ""
            title = refreshed.title
            chunk_count = await chunk_repo.count_child_chunks_for_document(refreshed.id)
            if chunk_count <= 0:
                await self._mark_job_document_failed(
                    db,
                    job_id=job_id,
                    document_id=document_id,
                    expected_content_hash=expected_content_hash,
                    error_message="文档缺少新的 child chunks，请删除后重新上传",
                )
                logger.warning(
                    "Skipped indexing for doc_id={} because no persisted child chunks were found",
                    document_id,
                )
                continue
            prepared.append(
                {
                    "document_id": refreshed.id,
                    "expected_content_hash": expected_content_hash,
                    "content": content,
                    "title": title,
                    "char_count": len(content),
                    "chunk_count": chunk_count,
                }
            )

        return prepared

    async def _run_document_batch_index(
        self,
        db: AsyncSession,
        *,
        batch: Sequence[dict[str, Any]],
        job_id: int | None = None,
    ) -> dict[int, int]:
        prepared_documents = [
            (
                int(item["document_id"]),
                str(item["content"]),
                item.get("title"),
            )
            for item in batch
        ]
        counts = await index_prepared_documents_batch(
            db,
            prepared_documents,
            commit=False,
        )
        current_hashes = await self._get_document_hashes(
            db,
            [int(item["document_id"]) for item in batch],
        )
        indexed_at = utc_now()
        finalized_counts: dict[int, int] = {}
        job_outcomes: list[tuple[int, str, str, Any | None, str | None]] = []

        for item in batch:
            document_id = int(item["document_id"])
            expected_content_hash = str(item["expected_content_hash"])
            current_hash = current_hashes.get(document_id)
            if current_hash != expected_content_hash:
                await delete_by_document_id(db, document_id, commit=False)
                job_outcomes.append(
                    (
                        document_id,
                        expected_content_hash,
                        INDEX_JOB_DOCUMENT_STATUS_FAILED,
                        None,
                        "文档内容已变化，索引结果已丢弃",
                    )
                )
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
            job_outcomes.append(
                (
                    document_id,
                    expected_content_hash,
                    INDEX_JOB_DOCUMENT_STATUS_INDEXED,
                    indexed_at,
                    None,
                )
            )

        await db.commit()

        if job_id is not None and job_outcomes:
            repo = IndexJobRepository(db)
            for document_id, expected_content_hash, status, item_indexed_at, error_message in job_outcomes:
                await repo.set_document_status(
                    job_id=job_id,
                    document_id=document_id,
                    expected_content_hash=expected_content_hash,
                    status=status,
                    error_message=error_message,
                    indexed_at=item_indexed_at,
                    refresh_job=False,
                )
            await repo.refresh_job_state(job_id=job_id)
        return finalized_counts

    async def index_document_task(
        self,
        *,
        document_id: int,
        expected_content_hash: str,
        job_id: int,
    ) -> None:
        """Background entrypoint for one document."""
        async with AsyncSessionLocal() as db:
            repo = IndexJobRepository(db)
            await repo.refresh_job_state(job_id=job_id)
            if not await repo.is_job_active(job_id=job_id):
                logger.info("Skipped inactive indexing job job_id={}", job_id)
                return
            await self._run_document_index(
                db,
                document_id=document_id,
                expected_content_hash=expected_content_hash,
                job_id=job_id,
            )

    async def index_documents_batch_task(
        self,
        *,
        documents: Sequence[tuple[int, str]],
        job_id: int,
    ) -> None:
        """Background entrypoint for multiple documents."""
        async with AsyncSessionLocal() as db:
            repo = IndexJobRepository(db)
            await repo.refresh_job_state(job_id=job_id)
            if not await repo.is_job_active(job_id=job_id):
                logger.info("Skipped inactive batch indexing job job_id={}", job_id)
                return
            prepared = await self._prepare_batch_candidates(db, documents, job_id=job_id)
            batches = self._build_dynamic_batches(prepared)

            for batch in batches:
                await repo.refresh_job_state(job_id=job_id)
                if not await repo.is_job_active(job_id=job_id):
                    logger.info("Stopped inactive batch indexing job job_id={}", job_id)
                    return
                try:
                    counts = await self._run_document_batch_index(db, batch=batch, job_id=job_id)
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
                            job_id=job_id,
                        )

    async def reindex_current_document_task(
        self,
        *,
        target_document_id: int,
        target_content_hash: str,
        job_id: int,
        previous_document_id: int | None = None,
    ) -> None:
        """Background entrypoint for current-version switches and new versions."""
        async with AsyncSessionLocal() as db:
            repo = IndexJobRepository(db)
            await repo.refresh_job_state(job_id=job_id)
            if not await repo.is_job_active(job_id=job_id):
                logger.info("Skipped inactive current-version reindex job job_id={}", job_id)
                return
            try:
                if previous_document_id and previous_document_id != target_document_id:
                    previous = await self._get_document(db, previous_document_id)
                    if previous and not getattr(previous, "is_live", False):
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
                    job_id=job_id,
                )
            except Exception as exc:
                await db.rollback()
                await self._mark_job_document_failed(
                    db,
                    job_id=job_id,
                    document_id=target_document_id,
                    expected_content_hash=target_content_hash,
                    error_message=self._truncate_error(exc),
                )
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
        job_id = await self.enqueue_documents_batch_job(
            db=db,
            user_id=user_id,
            documents=queued_docs,
            knowledge_base_id=knowledge_base_id if knowledge_base_id is not None else None,
            title="批量重建索引" if knowledge_base_id is not None else "全量重建索引",
            job_type="reindex_all_documents",
        )
        logger.info("Queued full reindex for {} documents", len(queued_docs))
        return {
            "message": f"Queued {len(queued_docs)} documents for reindexing",
            "queued": len(queued_docs),
            "job_id": job_id or 0,
        }

    async def index_single_document(
        self,
        *,
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
        job_id = await self.enqueue_document_job(
            db=db,
            user_id=user_id,
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
            knowledge_base_id=getattr(doc, "knowledge_base_id", None),
            title=f"重新索引《{doc.title}》",
            job_type="index_single_document",
        )
        return {
            "message": "Document queued for indexing",
            "queued": 1,
            "job_id": job_id,
        }


indexing_service = IndexingService()
