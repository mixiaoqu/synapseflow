"""Repository helpers for persisted indexing jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, IndexJob, IndexJobDocument, KnowledgeBase
from app.services.index_job_state import (
    ACTIVE_INDEX_JOB_STATUSES,
    INDEX_JOB_DOCUMENT_STATUS_FAILED,
    INDEX_JOB_DOCUMENT_STATUS_INDEXED,
    INDEX_JOB_DOCUMENT_STATUS_PROCESSING,
    INDEX_JOB_DOCUMENT_STATUS_QUEUED,
    INDEX_JOB_STATUS_COMPLETED,
    INDEX_JOB_STATUS_FAILED,
    INDEX_JOB_STATUS_PARTIAL_FAILED,
    INDEX_JOB_STATUS_PROCESSING,
    INDEX_JOB_STATUS_QUEUED,
)
from app.utils.time import utc_now


@dataclass(slots=True)
class ActiveIndexingJobRecord:
    job_id: int
    title: str
    job_type: str
    job_status: str
    knowledge_base_id: int | None
    knowledge_base_name: str | None
    queued: int
    processing: int
    indexed: int
    failed: int
    total: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class RecentFailedJobDocumentRecord:
    job_id: int
    document_id: int
    title: str
    job_title: str
    knowledge_base_id: int | None
    knowledge_base_name: str | None
    index_error: str | None
    updated_at: datetime


class IndexJobRepository:
    """Encapsulates indexing job persistence and aggregation."""

    def __init__(self, db: AsyncSession, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    async def create_job(
        self,
        *,
        user_id: int,
        title: str,
        job_type: str,
        knowledge_base_id: int | None,
        documents: list[tuple[int, str]],
    ) -> IndexJob:
        total = len(documents)
        job = IndexJob(
            user_id=user_id,
            title=title,
            job_type=job_type,
            knowledge_base_id=knowledge_base_id,
            status=INDEX_JOB_STATUS_QUEUED,
            total_documents=total,
            queued_documents=total,
            processing_documents=0,
            indexed_documents=0,
            failed_documents=0,
            started_at=None,
            finished_at=None,
        )
        self.db.add(job)
        await self.db.flush()

        self.db.add_all(
            [
                IndexJobDocument(
                    job_id=job.id,
                    document_id=document_id,
                    expected_content_hash=expected_content_hash,
                    status=INDEX_JOB_DOCUMENT_STATUS_QUEUED,
                    error_message=None,
                    indexed_at=None,
                )
                for document_id, expected_content_hash in documents
            ]
        )
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def set_document_status(
        self,
        *,
        job_id: int,
        document_id: int,
        expected_content_hash: str,
        status: str,
        error_message: str | None = None,
        indexed_at: datetime | None = None,
        refresh_job: bool = True,
    ) -> bool:
        result = await self.db.execute(
            update(IndexJobDocument)
            .where(
                IndexJobDocument.job_id == job_id,
                IndexJobDocument.document_id == document_id,
                IndexJobDocument.expected_content_hash == expected_content_hash,
            )
            .values(
                status=status,
                error_message=error_message,
                indexed_at=indexed_at,
            )
        )
        if not result.rowcount:
            await self.db.rollback()
            return False

        if refresh_job:
            await self.refresh_job_state(job_id=job_id)
        else:
            await self.db.flush()
        return True

    async def get_document_statuses(
        self,
        *,
        job_id: int,
        documents: list[tuple[int, str]],
    ) -> dict[tuple[int, str], str]:
        if not documents:
            return {}

        document_ids = [document_id for document_id, _ in documents]
        result = await self.db.execute(
            select(
                IndexJobDocument.document_id,
                IndexJobDocument.expected_content_hash,
                IndexJobDocument.status,
            ).where(
                IndexJobDocument.job_id == job_id,
                IndexJobDocument.document_id.in_(document_ids),
            )
        )
        return {
            (int(row.document_id), str(row.expected_content_hash)): str(row.status)
            for row in result
        }

    async def refresh_job_state(self, *, job_id: int) -> None:
        queued_count = func.sum(
            case((IndexJobDocument.status == INDEX_JOB_DOCUMENT_STATUS_QUEUED, 1), else_=0)
        )
        processing_count = func.sum(
            case((IndexJobDocument.status == INDEX_JOB_DOCUMENT_STATUS_PROCESSING, 1), else_=0)
        )
        indexed_count = func.sum(
            case((IndexJobDocument.status == INDEX_JOB_DOCUMENT_STATUS_INDEXED, 1), else_=0)
        )
        failed_count = func.sum(
            case((IndexJobDocument.status == INDEX_JOB_DOCUMENT_STATUS_FAILED, 1), else_=0)
        )
        result = await self.db.execute(
            select(
                func.count(IndexJobDocument.id).label("total"),
                queued_count.label("queued"),
                processing_count.label("processing"),
                indexed_count.label("indexed"),
                failed_count.label("failed"),
            ).where(IndexJobDocument.job_id == job_id)
        )
        counts = result.one()
        total = counts.total or 0
        queued = counts.queued or 0
        processing = counts.processing or 0
        indexed = counts.indexed or 0
        failed = counts.failed or 0
        completed = indexed + failed
        now = utc_now()

        if total <= 0:
            status = INDEX_JOB_STATUS_COMPLETED
        elif completed >= total:
            if failed >= total:
                status = INDEX_JOB_STATUS_FAILED
            elif failed > 0:
                status = INDEX_JOB_STATUS_PARTIAL_FAILED
            else:
                status = INDEX_JOB_STATUS_COMPLETED
        elif processing > 0 or indexed > 0 or failed > 0:
            status = INDEX_JOB_STATUS_PROCESSING
        else:
            status = INDEX_JOB_STATUS_QUEUED

        job = await self.db.get(IndexJob, job_id)
        started_at = job.started_at if job else None
        if started_at is None and status != INDEX_JOB_STATUS_QUEUED:
            started_at = now
        finished_at = now if completed >= total and total > 0 else None

        await self.db.execute(
            update(IndexJob)
            .where(IndexJob.id == job_id)
            .values(
                status=status,
                total_documents=total,
                queued_documents=queued,
                processing_documents=processing,
                indexed_documents=indexed,
                failed_documents=failed,
                started_at=started_at,
                finished_at=finished_at,
            )
        )
        await self.db.commit()

    async def mark_job_dispatch_failed(self, *, job_id: int, error_message: str) -> None:
        await self.db.execute(
            update(IndexJobDocument)
            .where(
                IndexJobDocument.job_id == job_id,
                IndexJobDocument.status.in_(
                    (
                        INDEX_JOB_DOCUMENT_STATUS_QUEUED,
                        INDEX_JOB_DOCUMENT_STATUS_PROCESSING,
                    )
                ),
            )
            .values(
                status=INDEX_JOB_DOCUMENT_STATUS_FAILED,
                error_message=error_message,
                indexed_at=None,
            )
        )
        await self.refresh_job_state(job_id=job_id)

    async def get_job_status(self, *, job_id: int) -> str | None:
        result = await self.db.execute(select(IndexJob.status).where(IndexJob.id == job_id))
        return result.scalar_one_or_none()

    async def is_job_active(self, *, job_id: int) -> bool:
        status = await self.get_job_status(job_id=job_id)
        return status in ACTIVE_INDEX_JOB_STATUSES

    async def refresh_active_jobs_for_user(self) -> None:
        if self.user_id is None:
            return
        result = await self.db.execute(
            select(IndexJob.id).where(
                IndexJob.user_id == self.user_id,
                IndexJob.status.in_(ACTIVE_INDEX_JOB_STATUSES),
            )
        )
        for job_id in result.scalars().all():
            await self.refresh_job_state(job_id=int(job_id))

    async def cancel_active_jobs_for_knowledge_base(
        self,
        *,
        knowledge_base_id: int,
        error_message: str,
    ) -> int:
        stmt = select(IndexJob.id).where(
            IndexJob.knowledge_base_id == knowledge_base_id,
            IndexJob.status.in_(ACTIVE_INDEX_JOB_STATUSES),
        )
        if self.user_id is not None:
            stmt = stmt.where(IndexJob.user_id == self.user_id)
        result = await self.db.execute(stmt)
        job_ids = [int(job_id) for job_id in result.scalars().all()]
        for job_id in job_ids:
            await self.mark_job_dispatch_failed(job_id=job_id, error_message=error_message)
        return len(job_ids)

    async def list_active_jobs(self, *, limit: int = 5) -> list[ActiveIndexingJobRecord]:
        if self.user_id is None:
            return []
        stmt = (
            select(
                IndexJob.id.label("job_id"),
                IndexJob.title.label("title"),
                IndexJob.job_type.label("job_type"),
                IndexJob.status.label("job_status"),
                IndexJob.knowledge_base_id.label("knowledge_base_id"),
                KnowledgeBase.name.label("knowledge_base_name"),
                IndexJob.queued_documents.label("queued"),
                IndexJob.processing_documents.label("processing"),
                IndexJob.indexed_documents.label("indexed"),
                IndexJob.failed_documents.label("failed"),
                IndexJob.total_documents.label("total"),
                IndexJob.created_at.label("created_at"),
                IndexJob.updated_at.label("updated_at"),
            )
            .outerjoin(KnowledgeBase, IndexJob.knowledge_base_id == KnowledgeBase.id)
            .where(
                IndexJob.user_id == self.user_id,
                IndexJob.status.in_(ACTIVE_INDEX_JOB_STATUSES),
            )
            .order_by(IndexJob.updated_at.desc(), IndexJob.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            ActiveIndexingJobRecord(
                job_id=row.job_id,
                title=row.title,
                job_type=row.job_type,
                job_status=row.job_status,
                knowledge_base_id=row.knowledge_base_id,
                knowledge_base_name=row.knowledge_base_name,
                queued=row.queued or 0,
                processing=row.processing or 0,
                indexed=row.indexed or 0,
                failed=row.failed or 0,
                total=row.total or 0,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in result
        ]

    async def list_recent_failed_documents(
        self,
        *,
        limit: int = 5,
    ) -> list[RecentFailedJobDocumentRecord]:
        if self.user_id is None:
            return []
        stmt = (
            select(
                IndexJobDocument.job_id.label("job_id"),
                IndexJobDocument.document_id.label("document_id"),
                Document.title.label("title"),
                IndexJob.title.label("job_title"),
                IndexJob.knowledge_base_id.label("knowledge_base_id"),
                KnowledgeBase.name.label("knowledge_base_name"),
                IndexJobDocument.error_message.label("index_error"),
                IndexJobDocument.updated_at.label("updated_at"),
            )
            .join(IndexJob, IndexJobDocument.job_id == IndexJob.id)
            .join(Document, IndexJobDocument.document_id == Document.id)
            .outerjoin(KnowledgeBase, IndexJob.knowledge_base_id == KnowledgeBase.id)
            .where(
                IndexJob.user_id == self.user_id,
                IndexJobDocument.status == INDEX_JOB_DOCUMENT_STATUS_FAILED,
            )
            .order_by(IndexJobDocument.updated_at.desc(), IndexJobDocument.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            RecentFailedJobDocumentRecord(
                job_id=row.job_id,
                document_id=row.document_id,
                title=row.title,
                job_title=row.job_title,
                knowledge_base_id=row.knowledge_base_id,
                knowledge_base_name=row.knowledge_base_name,
                index_error=row.index_error,
                updated_at=row.updated_at,
            )
            for row in result
        ]
