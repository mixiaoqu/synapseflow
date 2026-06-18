"""Application service for document persistence and document-facing workflows."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Sequence

from fastapi import HTTPException, UploadFile
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.indexing_service import indexing_service
from app.db.models import Document
from app.models.schemas.document import (
    ActiveIndexingJob,
    BatchDocumentActionFailure,
    BatchDocumentActionResponse,
    BatchDocumentFilterRequest,
    DocumentChunkResponse,
    DocumentChunksResponse,
    DocumentContentUpdate,
    DocumentCreate,
    DocumentListItem,
    DocumentListResponse,
    DocumentResponse,
    DocumentVersionItem,
    DocumentVersionsResponse,
    FailedIndexingItem,
    IndexingPanelSummaryResponse,
)
from app.repositories.document_category_repository import DocumentCategoryRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.index_job_repository import IndexJobRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.services.document_file_storage import StagedDocumentFile, document_file_storage
from app.services.document_index_state import (
    INDEX_STATUS_FAILED,
    INDEX_STATUS_QUEUED,
    is_indexed_status,
)
from app.services.document_indexer import persist_document_chunk_plan, prepare_document_chunk_plan
from app.services.document_lifecycle import (
    DOC_STATUS_ARCHIVED,
    DOC_STATUS_DRAFT,
    DOC_STATUS_PENDING_REVIEW,
    DOC_STATUS_PUBLISHED,
)
from app.services.document_parse_state import (
    PARSE_STATUS_FAILED,
    PARSE_STATUS_PARSED,
    PARSE_STATUS_QUEUED,
)
from app.services.graph_index_state import GRAPH_INDEX_STATUS_FAILED
from app.services.graph_store import get_graph_store
from app.services.vector_store import delete_by_document_id
from app.utils.document_parse import (
    MAX_FILE_SIZE,
    SUPPORTED_EXTENSIONS,
    ParsedDocument,
    parse_raw_document_content,
    render_parsed_document,
)

MAX_BATCH_UPLOAD_FILES = 500


class DocumentService:
    """Coordinates document CRUD and delegates indexing orchestration."""

    @staticmethod
    async def _delete_graph_for_documents(docs: Sequence[Document]) -> None:
        if not docs:
            return
        store = get_graph_store()
        seen_ids: set[int] = set()
        for doc in docs:
            document_id = int(doc.id)
            if document_id in seen_ids:
                continue
            seen_ids.add(document_id)
            await store.delete_document_graph(document_id=document_id)

    @staticmethod
    def _is_current_document(doc: Document) -> bool:
        return bool(getattr(doc, "is_current", True))

    @staticmethod
    def _http_error_detail(error: Exception) -> str:
        if isinstance(error, HTTPException):
            detail = error.detail
            return detail if isinstance(detail, str) else str(detail)
        return str(error) or "Unexpected error"

    @classmethod
    def _assert_current_document(cls, doc: Document) -> None:
        if not cls._is_current_document(doc):
            raise HTTPException(
                status_code=400,
                detail="Only the current working version can enter the review and publish flow",
            )

    @classmethod
    def _assert_can_submit_for_review(cls, doc: Document) -> None:
        cls._assert_current_document(doc)
        if not is_indexed_status(getattr(doc, "index_status", None)):
            raise HTTPException(
                status_code=400,
                detail="Document must finish indexing before it can be submitted for review",
            )
        if getattr(doc, "status", DOC_STATUS_DRAFT) != DOC_STATUS_DRAFT:
            raise HTTPException(
                status_code=400,
                detail="Only draft documents can be submitted for review",
            )

    @classmethod
    def _assert_can_reject(cls, doc: Document) -> None:
        cls._assert_current_document(doc)
        if getattr(doc, "status", DOC_STATUS_DRAFT) != DOC_STATUS_PENDING_REVIEW:
            raise HTTPException(
                status_code=400,
                detail="Only pending-review documents can be rejected",
            )

    @classmethod
    def _assert_can_publish(cls, doc: Document) -> None:
        cls._assert_current_document(doc)
        if not is_indexed_status(getattr(doc, "index_status", None)):
            raise HTTPException(
                status_code=400,
                detail="Document must finish indexing before publish",
            )
        if getattr(doc, "status", DOC_STATUS_DRAFT) not in (
            DOC_STATUS_PENDING_REVIEW,
            DOC_STATUS_ARCHIVED,
        ):
            raise HTTPException(
                status_code=400,
                detail="Document must be pending review or archived before publish",
            )

    @classmethod
    def _assert_can_unpublish(cls, doc: Document) -> None:
        if not getattr(doc, "is_live", False):
            raise HTTPException(
                status_code=400,
                detail="Only the live published version can be unpublished",
            )

    @staticmethod
    async def _resolve_document_team_id(
        *,
        db: AsyncSession,
        user_id: int,
        doc: Document,
    ) -> int | None:
        knowledge_base_id = getattr(doc, "knowledge_base_id", None)
        if knowledge_base_id is None:
            return None
        knowledge_base = await KnowledgeBaseRepository(db, user_id=user_id).get_by_id(knowledge_base_id)
        if knowledge_base is None:
            return None
        return getattr(knowledge_base, "team_id", None)

    @staticmethod
    def _get_title_and_type(filename: str) -> tuple[str, str]:
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if "." in filename:
            name, ext = filename.rsplit(".", 1)
            return name.strip() or filename, ext.lower()
        return filename, ""

    @staticmethod
    def _upload_extension(filename: str | None) -> str:
        safe_filename = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
        if "." not in safe_filename:
            return ""
        return "." + safe_filename.rsplit(".", 1)[-1].lower()

    @classmethod
    def _assert_supported_upload(cls, file: UploadFile, content: bytes) -> None:
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File exceeds the 10MB limit")

        ext = cls._upload_extension(file.filename)
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="不支持的文件格式: %s，支持 %s"
                % (ext or "无扩展名", ", ".join(sorted(SUPPORTED_EXTENSIONS))),
            )

    @classmethod
    def _is_supported_batch_upload(cls, file: UploadFile, content: bytes) -> bool:
        if len(content) > MAX_FILE_SIZE:
            return False
        return cls._upload_extension(file.filename) in SUPPORTED_EXTENSIONS

    @staticmethod
    def _parse_text_content(
        *,
        title: str,
        content: str,
        document_type: str | None,
    ) -> tuple[ParsedDocument, str]:
        parsed = parse_raw_document_content(
            content,
            title=title,
            document_type=document_type or "txt",
        )
        text = render_parsed_document(parsed)
        if not text.strip():
            raise HTTPException(status_code=400, detail="Document content cannot be empty")
        return parsed, text

    @staticmethod
    async def _persist_document_structure(
        *,
        db: AsyncSession,
        document_id: int,
        parsed_document: ParsedDocument,
        title: str,
    ) -> None:
        plan = prepare_document_chunk_plan(parsed_document, title)
        counts = await persist_document_chunk_plan(
            db,
            document_id=document_id,
            plan=plan,
        )
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 切片完成 doc_id={} title={} parent_chunks={} child_chunks={} chars={}",
            document_id,
            title,
            counts.get("parent", len(plan.parent_chunks)),
            counts.get("child", len(plan.child_chunks)),
            len(plan.full_text),
        )

    @staticmethod
    def _document_size(doc: Document) -> int:
        return getattr(doc, "size", 0) or len((doc.content or "").encode("utf-8"))

    @staticmethod
    def _display_title(title: str | None) -> str:
        normalized = (title or "").replace("\\", "/").strip()
        if not normalized:
            return "Untitled document"
        return normalized.rsplit("/", 1)[-1].strip() or normalized

    @staticmethod
    def _normalize_source_path(source_path: str | None) -> str | None:
        raw = (source_path or "").replace("\\", "/").strip().strip("/")
        if not raw:
            return None
        parts = [part.strip() for part in raw.split("/") if part.strip() and part.strip() != "."]
        if not parts:
            return None
        return str(PurePosixPath(*parts))

    @classmethod
    def _infer_category_parts(cls, source_path: str | None) -> tuple[str | None, str | None]:
        """Extract (parent_name, child_name) from source_path segments.

        "FolderA/SubFolder/file.txt" -> ("FolderA", "SubFolder")
        "FolderA/file.txt"           -> ("FolderA", None)
        "file.txt"                   -> (None, None)
        """
        normalized = cls._normalize_source_path(source_path)
        if not normalized or "/" not in normalized:
            return None, None
        parts = normalized.split("/")
        # parts[0..n-2] are folder segments, parts[-1] is the filename
        folder_parts = parts[:-1]
        parent_name = folder_parts[0].strip() or None if len(folder_parts) >= 1 else None
        child_name = folder_parts[1].strip() or None if len(folder_parts) >= 2 else None
        return parent_name, child_name

    async def _resolve_document_location(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        knowledge_base_id: int | None,
        category_id: int | None,
        source_path: str | None,
    ) -> tuple[int, int | None, str | None]:
        normalized_path = self._normalize_source_path(source_path)
        category_repo = DocumentCategoryRepository(db, user_id=user_id)
        knowledge_base_repo = KnowledgeBaseRepository(db, user_id=user_id)
        if knowledge_base_id is None:
            raise HTTPException(status_code=400, detail="Knowledge base is required")
        knowledge_base = await knowledge_base_repo.get_by_id(knowledge_base_id)
        if not knowledge_base:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        category = None
        if category_id is not None:
            category = await category_repo.get_by_id(category_id)
            if not category:
                raise HTTPException(status_code=404, detail="Category not found")
            if category.knowledge_base_id != knowledge_base_id:
                raise HTTPException(
                    status_code=400,
                    detail="Category does not belong to the selected knowledge base",
                )
        else:
            parent_name, child_name = self._infer_category_parts(normalized_path)
            if parent_name:
                parent_cat = await category_repo.get_or_create(
                    knowledge_base_id=knowledge_base_id,
                    name=parent_name,
                    parent_id=None,
                )
                if child_name:
                    category = await category_repo.get_or_create(
                        knowledge_base_id=knowledge_base_id,
                        name=child_name,
                        parent_id=parent_cat.id,
                    )
                else:
                    category = parent_cat
        return knowledge_base_id, category.id if category else None, normalized_path

    def _to_response(
        self,
        doc: Document,
        *,
        category_name: str | None = None,
    ) -> DocumentResponse:
        return DocumentResponse(
            id=doc.id,
            title=self._display_title(doc.title),
            content=doc.content or "",
            document_type=doc.document_type,
            size=self._document_size(doc),
            version=getattr(doc, "version", 1),
            is_current=getattr(doc, "is_current", True),
            is_latest=getattr(doc, "is_latest", True),
            is_live=getattr(doc, "is_live", False),
            knowledge_base_id=getattr(doc, "knowledge_base_id", None),
            category_id=getattr(doc, "category_id", None),
            category_name=category_name,
            source_path=getattr(doc, "source_path", None),
            status=getattr(doc, "status", DOC_STATUS_DRAFT),
            published_at=getattr(doc, "published_at", None),
            published_by=getattr(doc, "published_by", None),
            reviewed_at=getattr(doc, "reviewed_at", None),
            reviewed_by=getattr(doc, "reviewed_by", None),
            parse_status=getattr(doc, "parse_status", PARSE_STATUS_PARSED),
            parse_error=getattr(doc, "parse_error", None),
            parsed_at=getattr(doc, "parsed_at", None),
            index_status=getattr(doc, "index_status", INDEX_STATUS_QUEUED),
            index_error=getattr(doc, "index_error", None),
            indexed_at=getattr(doc, "indexed_at", None),
            graph_index_status=getattr(doc, "graph_index_status", INDEX_STATUS_QUEUED),
            graph_index_error=getattr(doc, "graph_index_error", None),
            graph_indexed_at=getattr(doc, "graph_indexed_at", None),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    async def upload_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        file: UploadFile,
        knowledge_base_id: int | None,
        category_id: int | None,
        source_path: str | None,
    ) -> DocumentResponse:
        content = await file.read()
        self._assert_supported_upload(file, content)

        title, doc_type = self._get_title_and_type(file.filename or "unknown")
        (
            knowledge_base_id,
            category_id,
            source_path,
        ) = await self._resolve_document_location(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            source_path=source_path,
        )
        repo = DocumentRepository(db, user_id=user_id)
        category_name = await repo.get_category_name(category_id)
        staged_path: str | None = None
        try:
            doc = await repo.create(
                title=title or "Untitled document",
                content="",
                document_type=doc_type or None,
                size=0,
                knowledge_base_id=knowledge_base_id,
                category_id=category_id,
                source_path=source_path,
                status=DOC_STATUS_DRAFT,
                commit=False,
            )
            staged_file = document_file_storage.save_uploaded_file(
                document_id=int(doc.id),
                filename=file.filename,
                content=content,
            )
            staged_path = staged_file.path
            self._apply_staged_file_metadata(doc, staged_file)
            await db.commit()
        except Exception:
            await db.rollback()
            document_file_storage.delete_staged_file(staged_path)
            raise
        await db.refresh(doc)
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 上传已受理 doc_id={} title={} staged_file={}",
            doc.id,
            doc.title,
            getattr(doc, "staged_file_path", None) or "-",
        )
        await self._enqueue_document_parse_task(db=db, doc=doc)
        logger.info("Uploaded document id={} title={}", doc.id, doc.title)
        return self._to_response(doc, category_name=category_name)

    async def upload_documents_batch(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        files: Sequence[UploadFile],
        knowledge_base_id: int | None,
        category_id: int | None,
        source_paths: Sequence[str] | None,
    ) -> list[DocumentResponse]:
        if len(files) > MAX_BATCH_UPLOAD_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"At most {MAX_BATCH_UPLOAD_FILES} files can be uploaded at once",
            )
        if source_paths is not None and len(source_paths) not in (0, len(files)):
            raise HTTPException(
                status_code=400,
                detail="source_paths must be empty or match the number of files",
            )

        repo = DocumentRepository(db, user_id=user_id)
        created: list[Document] = []
        category_names_by_doc_key: dict[int, str | None] = {}
        normalized_source_paths = list(source_paths or [])
        staged_paths: list[str] = []

        try:
            for index, file in enumerate(files):
                content = await file.read()
                if not self._is_supported_batch_upload(file, content):
                    continue
                title, doc_type = self._get_title_and_type(file.filename or "unknown")
                (
                    resolved_knowledge_base_id,
                    resolved_category_id,
                    normalized_source_path,
                ) = await self._resolve_document_location(
                    db=db,
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    category_id=category_id,
                    source_path=(
                        normalized_source_paths[index]
                        if index < len(normalized_source_paths)
                        else None
                    ),
                )
                category_name = await repo.get_category_name(resolved_category_id)
                doc = await repo.create(
                    title=title or "Untitled document",
                    content="",
                    document_type=doc_type or None,
                    size=0,
                    knowledge_base_id=resolved_knowledge_base_id,
                    category_id=resolved_category_id,
                    source_path=normalized_source_path,
                    status=DOC_STATUS_DRAFT,
                    commit=False,
                )
                staged_file = document_file_storage.save_uploaded_file(
                    document_id=int(doc.id),
                    filename=file.filename,
                    content=content,
                )
                staged_paths.append(staged_file.path)
                self._apply_staged_file_metadata(doc, staged_file)
                created.append(doc)
                category_names_by_doc_key[id(doc)] = category_name
            await db.commit()
        except HTTPException:
            await db.rollback()
            for staged_path in staged_paths:
                document_file_storage.delete_staged_file(staged_path)
            raise
        except Exception:
            await db.rollback()
            for staged_path in staged_paths:
                document_file_storage.delete_staged_file(staged_path)
            logger.exception("Batch upload aborted due to unexpected error")
            raise
        for doc in created:
            await db.refresh(doc)
        for doc in created:
            await self._enqueue_document_parse_task(db=db, doc=doc)
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 批量上传已受理 docs={}",
            len(created),
        )
        return [
            self._to_response(
                doc,
                category_name=category_names_by_doc_key.get(id(doc)),
            )
            for doc in created
        ]

    async def create_document_from_content(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        body: DocumentCreate,
    ) -> DocumentResponse:
        if not body.content.strip():
            raise HTTPException(status_code=400, detail="Document content cannot be empty")

        title = (body.title or "").strip() or "Untitled document"
        parsed, text = self._parse_text_content(
            title=title,
            content=body.content,
            document_type=body.document_type,
        )

        (
            knowledge_base_id,
            category_id,
            source_path,
        ) = await self._resolve_document_location(
            db=db,
            user_id=user_id,
            knowledge_base_id=body.knowledge_base_id,
            category_id=body.category_id,
            source_path=body.source_path,
        )
        category_name = await DocumentRepository(db, user_id=user_id).get_category_name(category_id)
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.create(
            title=title,
            content=text,
            document_type=body.document_type or "txt",
            size=len(text.encode("utf-8")),
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            source_path=source_path,
            status=DOC_STATUS_PENDING_REVIEW,
            commit=False,
        )
        await self._persist_document_structure(
            db=db,
            document_id=doc.id,
            parsed_document=parsed,
            title=doc.title,
        )
        await db.commit()
        await db.refresh(doc)
        jobs = await indexing_service.enqueue_document_indexing_jobs(
            db=db,
            user_id=user_id,
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
            knowledge_base_id=knowledge_base_id,
            title=f"索引《{doc.title}》",
        )
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 索引任务已入队 doc_id={} title={} text_job_id={} graph_job_id={}",
            doc.id,
            doc.title,
            jobs.get("job_id", 0),
            jobs.get("graph_job_id", 0),
        )
        logger.info("Created document from content id={} title={}", doc.id, doc.title)
        return self._to_response(doc, category_name=category_name)

    async def list_documents(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        page: int,
        page_size: int,
        keyword: str | None,
        team_id: int | None,
        knowledge_base_id: int | None,
        category_id: int | None,
        status: str | None = None,
    ) -> DocumentListResponse:
        page = max(page, 1)
        page_size = 10 if page_size < 1 or page_size > 100 else page_size

        repo = DocumentRepository(db, user_id=user_id)
        status_counts = await repo.get_status_counts(
            keyword=keyword,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
        )
        rows, total = await repo.list_paginated(
            page=page,
            page_size=page_size,
            keyword=keyword,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            status=status,
        )
        items = [
            DocumentListItem(
                id=doc.id,
                title=self._display_title(doc.title),
                document_type=doc.document_type,
                size=self._document_size(doc),
                version=getattr(doc, "version", 1),
                is_current=getattr(doc, "is_current", True),
                is_latest=getattr(doc, "is_latest", True),
                is_live=getattr(doc, "is_live", False),
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                indexed=is_indexed_status(getattr(doc, "index_status", None)),
                parse_status=getattr(doc, "parse_status", PARSE_STATUS_PARSED),
                parse_error=getattr(doc, "parse_error", None),
                parsed_at=getattr(doc, "parsed_at", None),
                index_status=getattr(doc, "index_status", INDEX_STATUS_QUEUED),
                index_error=getattr(doc, "index_error", None),
                indexed_at=getattr(doc, "indexed_at", None),
                graph_index_status=getattr(doc, "graph_index_status", INDEX_STATUS_QUEUED),
                graph_index_error=getattr(doc, "graph_index_error", None),
                graph_indexed_at=getattr(doc, "graph_indexed_at", None),
                knowledge_base_id=getattr(doc, "knowledge_base_id", None),
                category_id=getattr(doc, "category_id", None),
                knowledge_base_name=knowledge_base_name,
                category_name=category_name,
                source_path=getattr(doc, "source_path", None),
                status=getattr(doc, "status", DOC_STATUS_DRAFT),
                published_at=getattr(doc, "published_at", None),
                published_by=getattr(doc, "published_by", None),
                reviewed_at=getattr(doc, "reviewed_at", None),
                reviewed_by=getattr(doc, "reviewed_by", None),
            )
            for doc, knowledge_base_name, category_name in rows
        ]
        return DocumentListResponse(items=items, total=total, page=page, page_size=page_size, status_counts=status_counts)

    async def get_indexing_panel_summary(
        self,
        *,
        db: AsyncSession,
        user_id: int,
    ) -> IndexingPanelSummaryResponse:
        repo = IndexJobRepository(db, user_id=user_id)
        await repo.refresh_active_jobs_for_user()
        job_rows = await repo.list_active_jobs(limit=5)
        active_jobs: list[ActiveIndexingJob] = []
        queued = 0
        processing = 0
        indexed = 0
        failed = 0
        total = 0
        for row in job_rows:
            scope_total = row.total or 0
            completed = (row.indexed or 0) + (row.failed or 0)
            progress_percent = 100 if scope_total <= 0 else int((completed * 100) / scope_total)
            active_jobs.append(
                ActiveIndexingJob(
                    job_id=row.job_id,
                    title=self._display_title(row.title),
                    job_type=row.job_type,
                    job_status=row.job_status,  # type: ignore[arg-type]
                    knowledge_base_id=row.knowledge_base_id,
                    knowledge_base_name=row.knowledge_base_name,
                    queued=row.queued or 0,
                    processing=row.processing or 0,
                    indexed=row.indexed or 0,
                    failed=row.failed or 0,
                    total=scope_total,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    progress_percent=max(0, min(100, progress_percent)),
                )
            )
            queued += row.queued or 0
            processing += row.processing or 0
            indexed += row.indexed or 0
            failed += row.failed or 0
            total += scope_total

        failed_docs = await repo.list_recent_failed_documents(limit=5)
        recent_failed = [
            FailedIndexingItem(
                job_id=item.job_id,
                document_id=item.document_id,
                title=self._display_title(item.title),
                job_title=item.job_title,
                knowledge_base_id=item.knowledge_base_id,
                knowledge_base_name=item.knowledge_base_name,
                index_error=item.index_error,
                updated_at=item.updated_at,
            )
            for item in failed_docs
        ]

        return IndexingPanelSummaryResponse(
            queued=queued,
            processing=processing,
            indexed=indexed,
            failed=failed,
            total=total,
            has_active=(queued + processing) > 0,
            active_job_count=len(active_jobs),
            active_jobs=active_jobs[:5],
            recent_failed=recent_failed,
        )

    async def get_document_versions(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentVersionsResponse:
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.get_by_id_for_user(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        version_docs = await repo.get_versions_by_doc_id(doc_id)
        items = [
            DocumentVersionItem(
                id=version_doc.id,
                title=self._display_title(version_doc.title),
                version=getattr(version_doc, "version", 1),
                is_latest=getattr(version_doc, "is_latest", True),
                is_current=getattr(version_doc, "is_current", True),
                is_live=getattr(version_doc, "is_live", False),
                created_at=version_doc.created_at,
            )
            for version_doc in version_docs
        ]
        return DocumentVersionsResponse(items=items)

    async def get_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.get_by_id_for_user(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        category_name = await repo.get_category_name(getattr(doc, "category_id", None))
        return self._to_response(doc, category_name=category_name)

    async def get_document_chunks(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentChunksResponse:
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.get_by_id_for_user(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        chunk_rows = await DocumentChunkRepository(db).get_child_chunks_for_document(doc_id)
        items = [
            DocumentChunkResponse(
                id=row.id,
                document_id=row.document_id,
                chunk_kind=row.chunk_kind,
                parent_chunk_id=row.parent_chunk_id,
                chunk_index=row.chunk_index,
                prev_chunk_id=row.prev_chunk_id,
                next_chunk_id=row.next_chunk_id,
                section_path=row.section_path,
                block_types=list(row.block_types or []),
                start_offset=row.start_offset,
                end_offset=row.end_offset,
                content=row.content or "",
                search_text=row.search_text or "",
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in chunk_rows
        ]
        return DocumentChunksResponse(items=items, total=len(items))

    async def reindex_all_documents(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        team_id: int | None = None,
        knowledge_base_id: int | None = None,
    ) -> dict[str, int | str]:
        return await indexing_service.reindex_all_documents(
            db=db,
            user_id=user_id,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )

    async def index_single_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> dict[str, int | str]:
        return await indexing_service.index_single_document(
            db=db,
            user_id=user_id,
            doc_id=doc_id,
        )

    async def replace_document_content(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
        body: DocumentContentUpdate,
    ) -> DocumentResponse:
        repo = DocumentRepository(db, user_id=user_id)
        existing = await repo.get_by_id_for_user(doc_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        if getattr(existing, "is_live", False):
            raise HTTPException(
                status_code=400,
                detail="Published live versions cannot be overwritten; create a new version instead",
            )
        if not getattr(existing, "is_latest", True) or not getattr(existing, "is_current", True):
            raise HTTPException(
                status_code=400,
                detail="Only the current latest version can be overwritten",
            )
        parsed, text = self._parse_text_content(
            title=existing.title,
            content=body.content,
            document_type=getattr(existing, "document_type", None),
        )
        doc = await repo.update_content(doc_id, text, commit=False)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        await self._persist_document_structure(
            db=db,
            document_id=doc.id,
            parsed_document=parsed,
            title=doc.title,
        )
        await db.commit()
        await db.refresh(doc)
        jobs = await indexing_service.enqueue_document_indexing_jobs(
            db=db,
            user_id=user_id,
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
            knowledge_base_id=getattr(doc, "knowledge_base_id", None),
            title=f"重新索引《{doc.title}》",
        )
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 内容替换后索引任务已入队 doc_id={} title={} text_job_id={} graph_job_id={}",
            doc.id,
            doc.title,
            jobs.get("job_id", 0),
            jobs.get("graph_job_id", 0),
        )
        logger.info("Replaced document content id={}", doc_id)
        category_name = await repo.get_category_name(getattr(doc, "category_id", None))
        return self._to_response(doc, category_name=category_name)

    async def create_document_version(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
        body: DocumentContentUpdate,
    ) -> DocumentResponse:
        repo = DocumentRepository(db, user_id=user_id)
        orig = await repo.get_by_id_for_user(doc_id)
        if not orig:
            raise HTTPException(status_code=404, detail="Source document not found")

        root_id = getattr(orig, "root_id", None) or orig.id
        current_doc = await repo.get_current_by_root_id(root_id)
        parsed, text = self._parse_text_content(
            title=getattr(orig, "title", None) or "Untitled document",
            content=body.content,
            document_type=getattr(orig, "document_type", None),
        )
        new_doc = await repo.create_version(doc_id, text, commit=False)
        if not new_doc:
            raise HTTPException(status_code=404, detail="Source document not found")
        await self._persist_document_structure(
            db=db,
            document_id=new_doc.id,
            parsed_document=parsed,
            title=new_doc.title,
        )
        await db.commit()
        await db.refresh(new_doc)
        jobs = await indexing_service.enqueue_current_document_indexing_jobs(
            db=db,
            user_id=user_id,
            target_document_id=new_doc.id,
            target_content_hash=new_doc.content_hash,
            knowledge_base_id=getattr(new_doc, "knowledge_base_id", None),
            title=f"重建当前版本《{new_doc.title}》",
            previous_document_id=(
                current_doc.id if current_doc and current_doc.id != new_doc.id else None
            ),
        )
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 新版本索引任务已入队 doc_id={} title={} text_job_id={} graph_job_id={}",
            new_doc.id,
            new_doc.title,
            jobs.get("job_id", 0),
            jobs.get("graph_job_id", 0),
        )
        logger.info("Created document version id={} from doc_id={}", new_doc.id, doc_id)
        category_name = await repo.get_category_name(getattr(new_doc, "category_id", None))
        return self._to_response(new_doc, category_name=category_name)

    async def switch_current_document_version(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        repo = DocumentRepository(db, user_id=user_id)
        target, previous_current = await repo.switch_current_version(doc_id, commit=True)
        if not target:
            raise HTTPException(status_code=404, detail="Document not found")
        jobs = await indexing_service.enqueue_current_document_indexing_jobs(
            db=db,
            user_id=user_id,
            target_document_id=target.id,
            target_content_hash=target.content_hash,
            knowledge_base_id=getattr(target, "knowledge_base_id", None),
            title=f"切换当前版本并重建《{target.title}》",
            previous_document_id=(
                previous_current.id
                if previous_current and previous_current.id != target.id
                else None
            ),
        )
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 当前版本切换索引任务已入队 doc_id={} title={} text_job_id={} graph_job_id={}",
            target.id,
            target.title,
            jobs.get("job_id", 0),
            jobs.get("graph_job_id", 0),
        )
        logger.info("Switched current document version id={}", target.id)
        category_name = await repo.get_category_name(getattr(target, "category_id", None))
        return self._to_response(target, category_name=category_name)

    async def submit_document_for_review(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        return await self._submit_document_for_review(
            db=db,
            user_id=user_id,
            doc_id=doc_id,
        )

    async def _submit_document_for_review(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        repo = DocumentRepository(db, user_id=user_id)
        existing = await repo.get_by_id_for_user(doc_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        self._assert_can_submit_for_review(existing)
        doc = await repo.update_status(
            doc_id,
            status=DOC_STATUS_PENDING_REVIEW,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        category_name = await repo.get_category_name(getattr(doc, "category_id", None))
        return self._to_response(doc, category_name=category_name)

    async def reject_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        return await self._reject_document(
            db=db,
            user_id=user_id,
            doc_id=doc_id,
        )

    async def _reject_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        repo = DocumentRepository(db, user_id=user_id)
        existing = await repo.get_by_id_for_user(doc_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        self._assert_can_reject(existing)
        doc = await repo.update_status(
            doc_id,
            status=DOC_STATUS_DRAFT,
            reviewer_id=user_id,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        category_name = await repo.get_category_name(getattr(doc, "category_id", None))
        return self._to_response(doc, category_name=category_name)

    async def publish_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        return await self._publish_document(
            db=db,
            user_id=user_id,
            doc_id=doc_id,
        )

    async def _publish_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        repo = DocumentRepository(db, user_id=user_id)
        existing = await repo.get_by_id_for_user(doc_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        self._assert_can_publish(existing)
        root_id = getattr(existing, "root_id", None) or existing.id
        previous_live = await repo.get_live_by_root_id(root_id)
        await repo.clear_live_flags_for_root_id(root_id, exclude_doc_id=existing.id)
        doc = await repo.update_status(
            doc_id,
            status=DOC_STATUS_PUBLISHED,
            reviewer_id=user_id,
            publisher_id=user_id,
            is_live=True,
            commit=False,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if (
            previous_live
            and previous_live.id != doc.id
            and not getattr(previous_live, "is_current", False)
        ):
            await delete_by_document_id(db, previous_live.id, commit=False)
        await db.commit()
        await db.refresh(doc)
        category_name = await repo.get_category_name(getattr(doc, "category_id", None))
        return self._to_response(doc, category_name=category_name)

    async def unpublish_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        return await self._unpublish_document(
            db=db,
            user_id=user_id,
            doc_id=doc_id,
        )

    async def _unpublish_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> DocumentResponse:
        repo = DocumentRepository(db, user_id=user_id)
        existing = await repo.get_by_id_for_user(doc_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        self._assert_can_unpublish(existing)
        doc = await repo.update_status(
            doc_id,
            status=DOC_STATUS_ARCHIVED,
            reviewer_id=user_id,
            publisher_id=None,
            is_live=False,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        category_name = await repo.get_category_name(getattr(doc, "category_id", None))
        return self._to_response(doc, category_name=category_name)

    async def _run_batch_document_action(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        ids: list[int],
        action: str,
    ) -> BatchDocumentActionResponse:
        if action == "submit_for_review":
            return await self._update_documents_status_batch(
                db=db,
                user_id=user_id,
                ids=ids,
                action=action,
                status=DOC_STATUS_PENDING_REVIEW,
                validator=self._assert_can_submit_for_review,
            )
        if action == "reject":
            return await self._update_documents_status_batch(
                db=db,
                user_id=user_id,
                ids=ids,
                action=action,
                status=DOC_STATUS_DRAFT,
                validator=self._assert_can_reject,
                reviewer_id=user_id,
            )
        if action == "publish":
            return await self._publish_documents_batch_status(
                db=db,
                user_id=user_id,
                ids=ids,
                action=action,
            )
        if action == "unpublish":
            return await self._update_documents_status_batch(
                db=db,
                user_id=user_id,
                ids=ids,
                action=action,
                status=DOC_STATUS_ARCHIVED,
                validator=self._assert_can_unpublish,
                reviewer_id=user_id,
                is_live=False,
            )
        raise ValueError(f"Unsupported batch document action: {action}")

    async def _update_documents_status_batch(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        ids: list[int],
        action: str,
        status: str,
        validator,
        reviewer_id: int | None = None,
        publisher_id: int | None = None,
        is_live: bool | None = None,
    ) -> BatchDocumentActionResponse:
        unique_ids = list(dict.fromkeys(ids))
        repo = DocumentRepository(db, user_id=user_id)
        docs = await repo.get_by_ids(unique_ids)
        docs_by_id = {doc.id: doc for doc in docs}
        succeeded_docs: list[Document] = []
        failures: list[BatchDocumentActionFailure] = []

        for doc_id in unique_ids:
            doc = docs_by_id.get(doc_id)
            if not doc:
                failures.append(
                    BatchDocumentActionFailure(
                        document_id=doc_id,
                        detail="Document not found",
                    )
                )
                continue
            try:
                validator(doc)
            except Exception as error:  # noqa: BLE001
                failures.append(
                    BatchDocumentActionFailure(
                        document_id=doc_id,
                        detail=self._http_error_detail(error),
                    )
                )
                continue
            succeeded_docs.append(doc)

        if succeeded_docs:
            await repo.update_documents_status(
                succeeded_docs,
                status=status,
                reviewer_id=reviewer_id,
                publisher_id=publisher_id,
                is_live=is_live,
            )
            await db.commit()

        succeeded_ids = [doc.id for doc in succeeded_docs]
        return BatchDocumentActionResponse(
            action=action,
            requested_count=len(ids),
            succeeded_count=len(succeeded_ids),
            failed_count=len(failures),
            succeeded_ids=succeeded_ids,
            failures=failures,
        )

    @staticmethod
    def _apply_staged_file_metadata(doc: Document, staged_file: StagedDocumentFile) -> None:
        doc.parse_status = PARSE_STATUS_QUEUED
        doc.parse_error = None
        doc.parse_started_at = None
        doc.parsed_at = None
        doc.staged_file_path = staged_file.path
        doc.staged_file_name = staged_file.filename
        doc.staged_file_size = staged_file.size
        doc.staged_file_hash = staged_file.content_hash

    async def _enqueue_document_parse_task(
        self,
        *,
        db: AsyncSession,
        doc: Document,
    ) -> None:
        from app.application.document_parse_service import document_parse_service

        expected_hash = str(getattr(doc, "staged_file_hash", "") or "")
        if not expected_hash:
            return
        try:
            document_parse_service.enqueue_document_parse_task(
                document_id=int(doc.id),
                expected_staged_file_hash=expected_hash,
            )
            logger.bind(document_pipeline_log=True).info(
                "[文档管线] 解析任务已入队 doc_id={} title={}",
                doc.id,
                doc.title,
            )
        except Exception as exc:
            error_message = self._http_error_detail(exc)
            doc.parse_status = PARSE_STATUS_FAILED
            doc.parse_error = error_message
            doc.index_status = INDEX_STATUS_FAILED
            doc.index_error = error_message
            doc.graph_index_status = GRAPH_INDEX_STATUS_FAILED
            doc.graph_index_error = error_message
            await db.commit()
            await db.refresh(doc)
            logger.warning("Document parse dispatch failed doc_id={}: {}", doc.id, exc)

    @staticmethod
    def _delete_staged_files_for_documents(docs: Sequence[Document]) -> None:
        for doc in docs:
            document_file_storage.delete_staged_file(getattr(doc, "staged_file_path", None))

    async def _publish_documents_batch_status(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        ids: list[int],
        action: str,
    ) -> BatchDocumentActionResponse:
        unique_ids = list(dict.fromkeys(ids))
        repo = DocumentRepository(db, user_id=user_id)
        docs = await repo.get_by_ids(unique_ids)
        docs_by_id = {doc.id: doc for doc in docs}
        succeeded_docs: list[Document] = []
        failures: list[BatchDocumentActionFailure] = []

        for doc_id in unique_ids:
            doc = docs_by_id.get(doc_id)
            if not doc:
                failures.append(
                    BatchDocumentActionFailure(
                        document_id=doc_id,
                        detail="Document not found",
                    )
                )
                continue
            try:
                self._assert_can_publish(doc)
            except Exception as error:  # noqa: BLE001
                failures.append(
                    BatchDocumentActionFailure(
                        document_id=doc_id,
                        detail=self._http_error_detail(error),
                    )
                )
                continue
            succeeded_docs.append(doc)

        if succeeded_docs:
            root_ids = {getattr(doc, "root_id", None) or doc.id for doc in succeeded_docs}
            succeeded_ids_set = {doc.id for doc in succeeded_docs}
            previous_live_docs = [
                doc
                for doc in await repo.get_live_by_root_ids(root_ids)
                if doc.id not in succeeded_ids_set and not getattr(doc, "is_current", False)
            ]
            await repo.clear_live_flags_for_root_ids(root_ids, exclude_doc_ids=succeeded_ids_set)
            await repo.update_documents_status(
                succeeded_docs,
                status=DOC_STATUS_PUBLISHED,
                reviewer_id=user_id,
                publisher_id=user_id,
                is_live=True,
            )
            for previous_live in previous_live_docs:
                await delete_by_document_id(db, previous_live.id, commit=False)
            await db.commit()

        succeeded_ids = [doc.id for doc in succeeded_docs]
        return BatchDocumentActionResponse(
            action=action,
            requested_count=len(ids),
            succeeded_count=len(succeeded_ids),
            failed_count=len(failures),
            succeeded_ids=succeeded_ids,
            failures=failures,
        )

    async def _run_batch_document_action_by_filter(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        action: str,
        keyword: str | None = None,
        team_id: int | None = None,
        knowledge_base_id: int | None = None,
        category_id: int | None = None,
        status: str | None = None,
    ) -> BatchDocumentActionResponse:
        repo = DocumentRepository(db, user_id=user_id)
        ids = await repo.list_ids(
            keyword=keyword,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            status=status,
        )
        return await self._run_batch_document_action(
            db=db,
            user_id=user_id,
            ids=ids,
            action=action,
        )

    async def submit_documents_for_review_batch(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        ids: list[int],
    ) -> BatchDocumentActionResponse:
        return await self._run_batch_document_action(
            db=db,
            user_id=user_id,
            ids=ids,
            action="submit_for_review",
        )

    async def submit_documents_for_review_by_filter(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        filter_body: BatchDocumentFilterRequest,
    ) -> BatchDocumentActionResponse:
        return await self._run_batch_document_action_by_filter(
            db=db,
            user_id=user_id,
            action="submit_for_review",
            keyword=filter_body.keyword,
            team_id=filter_body.team_id,
            knowledge_base_id=filter_body.knowledge_base_id,
            category_id=filter_body.category_id,
            status="draft",
        )

    async def reject_documents_batch(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        ids: list[int],
    ) -> BatchDocumentActionResponse:
        return await self._run_batch_document_action(
            db=db,
            user_id=user_id,
            ids=ids,
            action="reject",
        )

    async def publish_documents_batch(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        ids: list[int],
    ) -> BatchDocumentActionResponse:
        return await self._run_batch_document_action(
            db=db,
            user_id=user_id,
            ids=ids,
            action="publish",
        )

    async def publish_documents_by_filter(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        filter_body: BatchDocumentFilterRequest,
    ) -> BatchDocumentActionResponse:
        return await self._run_batch_document_action_by_filter(
            db=db,
            user_id=user_id,
            action="publish",
            keyword=filter_body.keyword,
            team_id=filter_body.team_id,
            knowledge_base_id=filter_body.knowledge_base_id,
            category_id=filter_body.category_id,
            status="pending_review",
        )

    async def unpublish_documents_batch(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        ids: list[int],
    ) -> BatchDocumentActionResponse:
        return await self._run_batch_document_action(
            db=db,
            user_id=user_id,
            ids=ids,
            action="unpublish",
        )

    async def delete_documents_batch(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        ids: list[int],
    ) -> dict[str, int | str]:
        if not ids:
            return {"message": "No documents selected", "deleted": 0}

        repo = DocumentRepository(db, user_id=user_id)
        docs = await repo.get_by_ids(ids)
        root_ids = {getattr(doc, "root_id", None) or doc.id for doc in docs}
        chain_docs = await repo.get_chain_by_root_ids(root_ids)
        await self._delete_graph_for_documents(chain_docs)
        self._delete_staged_files_for_documents(chain_docs)
        deleted = await repo.delete_chain(chain_docs)
        logger.info("Batch deleted documents ids={} deleted={}", ids, deleted)
        return {"message": f"Deleted {deleted} documents", "deleted": deleted}

    async def delete_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> dict[str, str]:
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.get_by_id_for_user(doc_id)
        if not doc:
            count = await repo.count_total()
            raise HTTPException(
                status_code=404,
                detail=f"Document not found: id={doc_id}, current total={count}",
            )

        root_id = getattr(doc, "root_id", None) or doc.id
        chain_docs = await repo.get_chain_by_root_ids({root_id})
        await self._delete_graph_for_documents(chain_docs)
        self._delete_staged_files_for_documents(chain_docs)
        await repo.delete_chain(chain_docs)
        logger.info("Deleted document id={} chain_size={}", doc_id, len(chain_docs))
        return {"message": "Deleted successfully"}


document_service = DocumentService()
