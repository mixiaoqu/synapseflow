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
    DocumentContentUpdate,
    DocumentCreate,
    FailedIndexingItem,
    DocumentListItem,
    DocumentListResponse,
    DocumentResponse,
    DocumentVersionItem,
    DocumentVersionsResponse,
    IndexingPanelSummaryResponse,
)
from app.repositories.document_category_repository import DocumentCategoryRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.index_job_repository import IndexJobRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.services.document_index_state import (
    INDEX_STATUS_QUEUED,
    compute_content_hash,
    is_indexed_status,
)
from app.services.document_lifecycle import (
    DOC_STATUS_DRAFT,
    DOC_STATUS_PENDING_REVIEW,
    DOC_STATUS_PUBLISHED,
)
from app.services.document_indexer import persist_document_chunk_plan, prepare_document_chunk_plan
from app.services.sensitive_word_service import get_sensitive_word_service
from app.services.vector_store import delete_by_document_id
from app.utils.document_parse import (
    MAX_FILE_SIZE,
    ParsedDocument,
    SUPPORTED_EXTENSIONS,
    parse_raw_document_content,
    parse_uploaded_document_structured,
    render_parsed_document,
)

MAX_BATCH_UPLOAD_FILES = 500


class DocumentService:
    """Coordinates document CRUD and delegates indexing orchestration."""

    @staticmethod
    def _is_current_document(doc: Document) -> bool:
        return bool(getattr(doc, "is_current", True))

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
        if getattr(doc, "status", DOC_STATUS_DRAFT) != DOC_STATUS_PENDING_REVIEW:
            raise HTTPException(
                status_code=400,
                detail="Document must be pending review before publish",
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
        if "." in filename:
            name, ext = filename.rsplit(".", 1)
            return name.strip() or filename, ext.lower()
        return filename, ""

    def _parse_single_file(
        self,
        file: UploadFile,
        content: bytes,
    ) -> tuple[str, str | None, ParsedDocument, str]:
        filename = file.filename or "unknown"
        parsed, error = parse_uploaded_document_structured(filename, content)
        if error or parsed is None:
            raise HTTPException(status_code=400, detail=error or "Document parse failed")
        text = render_parsed_document(parsed)
        if not text.strip():
            raise HTTPException(status_code=400, detail=f"File '{filename}' is empty")
        title, doc_type = self._get_title_and_type(filename)
        return title or parsed.title or "Untitled document", doc_type or None, parsed, text

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
        await persist_document_chunk_plan(
            db,
            document_id=document_id,
            plan=plan,
        )

    @staticmethod
    def _document_size(doc: Document) -> int:
        return getattr(doc, "size", 0) or len((doc.content or "").encode("utf-8"))

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
    def _infer_category_name(cls, source_path: str | None) -> str | None:
        normalized = cls._normalize_source_path(source_path)
        if not normalized or "/" not in normalized:
            return None
        return normalized.split("/", 1)[0].strip() or None

    async def _resolve_document_location(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        knowledge_base_id: int | None,
        category_id: int | None,
        source_path: str | None,
    ) -> tuple[int | None, int | None, str | None, str | None]:
        normalized_path = self._normalize_source_path(source_path)
        category_repo = DocumentCategoryRepository(db, user_id=user_id)
        knowledge_base_repo = KnowledgeBaseRepository(db, user_id=user_id)
        category = None

        if category_id is not None:
            category = await category_repo.get_by_id(category_id)
            if not category:
                raise HTTPException(status_code=404, detail="Category not found")
            if knowledge_base_id is None:
                knowledge_base_id = category.knowledge_base_id
            elif category.knowledge_base_id != knowledge_base_id:
                raise HTTPException(
                    status_code=400,
                    detail="Category does not belong to the selected knowledge base",
                )
        elif knowledge_base_id is not None:
            knowledge_base = await knowledge_base_repo.get_by_id(knowledge_base_id)
            if not knowledge_base:
                raise HTTPException(status_code=404, detail="Knowledge base not found")
            inferred_name = self._infer_category_name(normalized_path)
            if inferred_name:
                category = await category_repo.get_or_create(
                    knowledge_base_id=knowledge_base_id,
                    name=inferred_name,
                )
        elif knowledge_base_id is None and category_id is None:
            return knowledge_base_id, None, None, normalized_path

        return (
            knowledge_base_id,
            category.id if category else None,
            category.name if category else None,
            normalized_path,
        )

    def _to_response(
        self,
        doc: Document,
        *,
        category_name: str | None = None,
    ) -> DocumentResponse:
        return DocumentResponse(
            id=doc.id,
            title=doc.title,
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
            index_status=getattr(doc, "index_status", INDEX_STATUS_QUEUED),
            index_error=getattr(doc, "index_error", None),
            indexed_at=getattr(doc, "indexed_at", None),
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
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File exceeds the 10MB limit")

        title, doc_type, parsed, text = self._parse_single_file(file, content)
        (
            knowledge_base_id,
            category_id,
            category_name,
            source_path,
        ) = await self._resolve_document_location(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            source_path=source_path,
        )
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.create(
            title=title,
            content=text,
            document_type=doc_type,
            size=len(text.encode("utf-8")),
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            source_path=source_path,
            status=DOC_STATUS_DRAFT,
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
        await indexing_service.enqueue_document_job(
            db=db,
            user_id=user_id,
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
            knowledge_base_id=knowledge_base_id,
            title=f"索引《{doc.title}》",
        )
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
        parsed_by_doc_key: dict[int, ParsedDocument] = {}
        normalized_source_paths = list(source_paths or [])

        for index, file in enumerate(files):
            try:
                content = await file.read()
                if len(content) > MAX_FILE_SIZE:
                    continue
                ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                title, doc_type, parsed, text = self._parse_single_file(file, content)
                (
                    resolved_knowledge_base_id,
                    resolved_category_id,
                    category_name,
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
                doc = Document(
                    user_id=repo.user_id,
                    title=title,
                    content=text,
                    document_type=doc_type,
                    size=len(text.encode("utf-8")),
                    content_hash=compute_content_hash(text),
                    index_status=INDEX_STATUS_QUEUED,
                    index_error=None,
                    indexed_at=None,
                    version=1,
                    parent_id=None,
                    is_latest=True,
                    is_current=True,
                    is_live=False,
                    knowledge_base_id=resolved_knowledge_base_id,
                    category_id=resolved_category_id,
                    source_path=normalized_source_path,
                    status=DOC_STATUS_DRAFT,
                )
                await repo.add_for_batch(doc)
                created.append(doc)
                category_names_by_doc_key[id(doc)] = category_name
                parsed_by_doc_key[id(doc)] = parsed
            except HTTPException:
                raise
            except Exception:
                logger.exception(
                    "Batch upload aborted for file={} due to unexpected error",
                    file.filename or "unknown",
                )
                raise

        await repo.prepare_batch_create(created)
        for doc in created:
            parsed = parsed_by_doc_key.get(id(doc))
            if parsed is None:
                continue
            await self._persist_document_structure(
                db=db,
                document_id=doc.id,
                parsed_document=parsed,
                title=doc.title,
            )
        await db.commit()
        for doc in created:
            await db.refresh(doc)
        if not created:
            return []
        await indexing_service.enqueue_documents_batch_job(
            db=db,
            user_id=user_id,
            documents=[(doc.id, doc.content_hash) for doc in created],
            knowledge_base_id=(
                created[0].knowledge_base_id
                if created and all(doc.knowledge_base_id == created[0].knowledge_base_id for doc in created)
                else None
            ),
            title=(
                f"索引《{created[0].title}》"
                if len(created) == 1
                else f"批量索引 {len(created)} 个文档"
            ),
        )
        return [
            self._to_response(doc, category_name=category_names_by_doc_key.get(id(doc)))
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
            category_name,
            source_path,
        ) = await self._resolve_document_location(
            db=db,
            user_id=user_id,
            knowledge_base_id=body.knowledge_base_id,
            category_id=body.category_id,
            source_path=body.source_path,
        )
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.create(
            title=title,
            content=text,
            document_type=body.document_type or "txt",
            size=len(text.encode("utf-8")),
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            source_path=source_path,
            status=DOC_STATUS_DRAFT,
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
        await indexing_service.enqueue_document_job(
            db=db,
            user_id=user_id,
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
            knowledge_base_id=knowledge_base_id,
            title=f"索引《{doc.title}》",
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
        page_size = 20 if page_size < 1 or page_size > 100 else page_size

        repo = DocumentRepository(db, user_id=user_id)
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
                title=doc.title,
                document_type=doc.document_type,
                size=self._document_size(doc),
                version=getattr(doc, "version", 1),
                is_current=getattr(doc, "is_current", True),
                is_latest=getattr(doc, "is_latest", True),
                is_live=getattr(doc, "is_live", False),
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                indexed=is_indexed_status(getattr(doc, "index_status", None)),
                index_status=getattr(doc, "index_status", INDEX_STATUS_QUEUED),
                index_error=getattr(doc, "index_error", None),
                indexed_at=getattr(doc, "indexed_at", None),
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
        return DocumentListResponse(items=items, total=total, page=page, page_size=page_size)

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
                    title=row.title,
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
                title=item.title,
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
                title=version_doc.title,
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
        await indexing_service.enqueue_document_job(
            db=db,
            user_id=user_id,
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
            knowledge_base_id=getattr(doc, "knowledge_base_id", None),
            title=f"重新索引《{doc.title}》",
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
        await indexing_service.enqueue_current_document_reindex_job(
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
        await indexing_service.enqueue_current_document_reindex_job(
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
        repo = DocumentRepository(db, user_id=user_id)
        existing = await repo.get_by_id_for_user(doc_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        self._assert_can_publish(existing)
        team_id = await self._resolve_document_team_id(db=db, user_id=user_id, doc=existing)
        sensitive_check = await get_sensitive_word_service().check_text(
            scene="document_publish",
            text=str(getattr(existing, "content", "") or ""),
            team_id=team_id,
            db=db,
        )
        if sensitive_check.blocked:
            matched = "、".join(sensitive_check.matched_words[:5])
            suffix = "等敏感词" if len(sensitive_check.matched_words) > 5 else "敏感词"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Document contains {matched}{suffix} and cannot be published"
                    if matched
                    else "Document contains sensitive content and cannot be published"
                ),
            )
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
        repo = DocumentRepository(db, user_id=user_id)
        existing = await repo.get_by_id_for_user(doc_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        self._assert_can_unpublish(existing)
        doc = await repo.update_status(
            doc_id,
            status=DOC_STATUS_DRAFT,
            reviewer_id=user_id,
            publisher_id=None,
            is_live=False,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        category_name = await repo.get_category_name(getattr(doc, "category_id", None))
        return self._to_response(doc, category_name=category_name)

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
        await repo.delete_chain(chain_docs)
        logger.info("Deleted document id={} chain_size={}", doc_id, len(chain_docs))
        return {"message": "Deleted successfully"}


document_service = DocumentService()
