"""Background document parsing orchestration."""

from __future__ import annotations

import asyncio
from importlib import import_module

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.indexing_service import indexing_service
from app.db.models import Document
from app.db.session import AsyncSessionLocal
from app.services.document_file_storage import document_file_storage
from app.services.document_index_state import (
    INDEX_STATUS_FAILED,
    INDEX_STATUS_QUEUED,
    compute_content_hash,
)
from app.services.document_indexer import persist_document_chunk_plan, prepare_document_chunk_plan
from app.services.document_lifecycle import DOC_STATUS_DRAFT, DOC_STATUS_PENDING_REVIEW
from app.services.document_parse_state import (
    PARSE_STATUS_FAILED,
    PARSE_STATUS_PARSED,
    PARSE_STATUS_PROCESSING,
)
from app.services.graph_index_state import GRAPH_INDEX_STATUS_FAILED, GRAPH_INDEX_STATUS_QUEUED
from app.utils.document_parse import parse_uploaded_document_structured, render_parsed_document
from app.utils.time import utc_now

MAX_PARSE_ERROR_LENGTH = 1000


class DocumentParseService:
    """Owns the uploaded-file parse task and hands parsed documents to indexing."""

    @staticmethod
    def _actor_module():
        return import_module("app.workers.indexing_tasks")

    @staticmethod
    def _truncate_error(error: Exception) -> str:
        return str(error).strip()[:MAX_PARSE_ERROR_LENGTH] or error.__class__.__name__

    def enqueue_document_parse_task(
        self,
        *,
        document_id: int,
        expected_staged_file_hash: str,
    ) -> None:
        self._actor_module().parse_document_actor.send(
            int(document_id),
            str(expected_staged_file_hash),
        )

    async def parse_document_task(
        self,
        *,
        document_id: int,
        expected_staged_file_hash: str,
    ) -> None:
        staged_file_path, staged_file_name = await self._claim_document_parse(
            document_id=document_id,
            expected_staged_file_hash=expected_staged_file_hash,
        )
        if not staged_file_path:
            return

        try:
            content = await asyncio.to_thread(
                document_file_storage.open_staged_file,
                staged_file_path,
            )
            parsed_document, error = await asyncio.to_thread(
                parse_uploaded_document_structured,
                staged_file_name,
                content,
            )
            if error or parsed_document is None:
                raise ValueError(error or "Document parse failed")

            rendered_content = render_parsed_document(parsed_document)
            if not rendered_content.strip():
                raise ValueError(f"File '{staged_file_name}' is empty")

            title = await self._get_document_title(document_id)
            chunk_plan = await asyncio.to_thread(
                prepare_document_chunk_plan,
                parsed_document,
                title or parsed_document.title,
            )
            content_hash = await self._persist_parse_result(
                document_id=document_id,
                expected_staged_file_hash=expected_staged_file_hash,
                rendered_content=rendered_content,
                chunk_plan=chunk_plan,
            )
        except Exception as exc:
            await self._mark_parse_failed(
                document_id=document_id,
                expected_staged_file_hash=expected_staged_file_hash,
                error_message=self._truncate_error(exc),
            )
            logger.warning("Document parse failed doc_id={}: {}", document_id, exc)
            return

        await self._enqueue_indexing_after_parse(
            document_id=document_id,
            expected_content_hash=content_hash,
        )
        if document_file_storage.delete_staged_file(staged_file_path):
            await self._clear_staged_file_path(
                document_id=document_id,
                expected_staged_file_hash=expected_staged_file_hash,
            )

    async def _claim_document_parse(
        self,
        *,
        document_id: int,
        expected_staged_file_hash: str,
    ) -> tuple[str | None, str]:
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, document_id)
            if doc is None:
                return None, ""
            if getattr(doc, "staged_file_hash", None) != expected_staged_file_hash:
                logger.info(
                    "Skip stale document parse task doc_id={} expected_hash={}",
                    document_id,
                    expected_staged_file_hash,
                )
                return None, ""
            staged_file_path = str(getattr(doc, "staged_file_path", "") or "")
            if not staged_file_path:
                await self._mark_loaded_document_failed(db, doc, "Missing staged document file path")
                await db.commit()
                return None, ""

            doc.parse_status = PARSE_STATUS_PROCESSING
            doc.parse_error = None
            doc.parse_started_at = utc_now()
            await db.commit()
            return staged_file_path, str(getattr(doc, "staged_file_name", None) or doc.title)

    async def _get_document_title(self, document_id: int) -> str | None:
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, document_id)
            return str(doc.title) if doc is not None else None

    async def _persist_parse_result(
        self,
        *,
        document_id: int,
        expected_staged_file_hash: str,
        rendered_content: str,
        chunk_plan,
    ) -> str:
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, document_id)
            if doc is None:
                return ""
            if getattr(doc, "staged_file_hash", None) != expected_staged_file_hash:
                raise ValueError(f"Document {document_id} staged file changed before parse result persist")

            doc.content = rendered_content
            doc.size = len(rendered_content.encode("utf-8"))
            doc.content_hash = compute_content_hash(rendered_content)
            doc.parse_status = PARSE_STATUS_PARSED
            doc.parse_error = None
            doc.parsed_at = utc_now()
            doc.index_status = INDEX_STATUS_QUEUED
            doc.index_error = None
            doc.indexed_at = None
            doc.graph_index_status = GRAPH_INDEX_STATUS_QUEUED
            doc.graph_index_error = None
            doc.graph_indexed_at = None
            if getattr(doc, "status", DOC_STATUS_DRAFT) == DOC_STATUS_DRAFT:
                doc.status = DOC_STATUS_PENDING_REVIEW

            counts = await persist_document_chunk_plan(
                db,
                document_id=document_id,
                plan=chunk_plan,
            )
            logger.bind(document_pipeline_log=True).info(
                "[文档管线] 后台解析切片完成 doc_id={} parent_chunks={} child_chunks={} chars={}",
                document_id,
                counts.get("parent", len(chunk_plan.parent_chunks)),
                counts.get("child", len(chunk_plan.child_chunks)),
                len(chunk_plan.full_text),
            )
            content_hash = str(doc.content_hash)
            await db.commit()
            return content_hash

    async def _enqueue_indexing_after_parse(
        self,
        *,
        document_id: int,
        expected_content_hash: str,
    ) -> None:
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, document_id)
            if doc is None or getattr(doc, "content_hash", None) != expected_content_hash:
                return
            try:
                jobs = await indexing_service.enqueue_document_indexing_jobs(
                    db=db,
                    user_id=int(doc.user_id),
                    document_id=int(doc.id),
                    expected_content_hash=expected_content_hash,
                    knowledge_base_id=getattr(doc, "knowledge_base_id", None),
                    title=f"索引《{doc.title}》",
                )
                logger.bind(document_pipeline_log=True).info(
                    "[文档管线] 解析后索引任务已入队 doc_id={} text_job_id={} graph_job_id={}",
                    document_id,
                    jobs.get("job_id", 0),
                    jobs.get("graph_job_id", 0),
                )
            except Exception as exc:
                logger.warning("Indexing dispatch after parse failed doc_id={}: {}", document_id, exc)

    async def _mark_parse_failed(
        self,
        *,
        document_id: int,
        expected_staged_file_hash: str,
        error_message: str,
    ) -> None:
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, document_id)
            if doc is None or getattr(doc, "staged_file_hash", None) != expected_staged_file_hash:
                return
            await self._mark_loaded_document_failed(db, doc, error_message)
            await db.commit()

    async def _clear_staged_file_path(
        self,
        *,
        document_id: int,
        expected_staged_file_hash: str,
    ) -> None:
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, document_id)
            if doc is None or getattr(doc, "staged_file_hash", None) != expected_staged_file_hash:
                return
            doc.staged_file_path = None
            await db.commit()

    async def _mark_loaded_document_failed(
        self,
        db: AsyncSession,
        doc: Document,
        error_message: str,
    ) -> None:
        doc.parse_status = PARSE_STATUS_FAILED
        doc.parse_error = error_message
        doc.index_status = INDEX_STATUS_FAILED
        doc.index_error = error_message
        doc.indexed_at = None
        doc.graph_index_status = GRAPH_INDEX_STATUS_FAILED
        doc.graph_index_error = error_message
        doc.graph_indexed_at = None
        if not getattr(doc, "parse_started_at", None):
            doc.parse_started_at = utc_now()
        await db.flush()


document_parse_service = DocumentParseService()
