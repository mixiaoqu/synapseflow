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
    DocumentContentUpdate,
    DocumentCreate,
    DocumentListItem,
    DocumentListResponse,
    DocumentResponse,
    DocumentVersionItem,
    DocumentVersionsResponse,
)
from app.repositories.document_category_repository import DocumentCategoryRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.services.document_index_state import (
    INDEX_STATUS_QUEUED,
    compute_content_hash,
    is_indexed_status,
)
from app.utils.file_parser import MAX_FILE_SIZE, SUPPORTED_EXTENSIONS, extract_text_from_file

MAX_BATCH_UPLOAD_FILES = 100


class DocumentService:
    """Coordinates document CRUD and delegates indexing orchestration."""

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
    ) -> tuple[str, str | None, str]:
        filename = file.filename or "unknown"
        text, err = extract_text_from_file(filename, content)
        if err:
            raise HTTPException(status_code=400, detail=err)
        if not text.strip():
            raise HTTPException(status_code=400, detail=f"File '{filename}' is empty")
        title, doc_type = self._get_title_and_type(filename)
        return title or "Untitled document", doc_type or None, text

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
            knowledge_base_id=getattr(doc, "knowledge_base_id", None),
            category_id=getattr(doc, "category_id", None),
            category_name=category_name,
            source_path=getattr(doc, "source_path", None),
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

        title, doc_type, text = self._parse_single_file(file, content)
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
            commit=True,
        )
        indexing_service.enqueue_document(
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
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
        normalized_source_paths = list(source_paths or [])

        for index, file in enumerate(files):
            try:
                content = await file.read()
                if len(content) > MAX_FILE_SIZE:
                    continue
                ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                title, doc_type, text = self._parse_single_file(file, content)
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
                    knowledge_base_id=resolved_knowledge_base_id,
                    category_id=resolved_category_id,
                    source_path=normalized_source_path,
                )
                await repo.add_for_batch(doc)
                created.append(doc)
                category_names_by_doc_key[id(doc)] = category_name
            except HTTPException:
                raise
            except Exception:
                continue

        await repo.commit_and_refresh_root_ids(created)
        indexing_service.enqueue_documents_batch(
            documents=[(doc.id, doc.content_hash) for doc in created],
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
            title=(body.title or "").strip() or "Untitled document",
            content=body.content,
            document_type=body.document_type or "txt",
            size=len(body.content.encode("utf-8")),
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            source_path=source_path,
            commit=True,
        )
        indexing_service.enqueue_document(
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
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
        )
        items = [
            DocumentListItem(
                id=doc.id,
                title=doc.title,
                document_type=doc.document_type,
                size=self._document_size(doc),
                version=getattr(doc, "version", 1),
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
            )
            for doc, knowledge_base_name, category_name in rows
        ]
        return DocumentListResponse(items=items, total=total, page=page, page_size=page_size)

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
        if not getattr(existing, "is_latest", True) or not getattr(existing, "is_current", True):
            raise HTTPException(
                status_code=400,
                detail="Only the current latest version can be overwritten",
            )
        doc = await repo.update_content(doc_id, body.content)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        indexing_service.enqueue_document(
            document_id=doc.id,
            expected_content_hash=doc.content_hash,
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
        new_doc = await repo.create_version(doc_id, body.content, commit=True)
        if not new_doc:
            raise HTTPException(status_code=404, detail="Source document not found")
        indexing_service.enqueue_current_document_reindex(
            target_document_id=new_doc.id,
            target_content_hash=new_doc.content_hash,
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
        indexing_service.enqueue_current_document_reindex(
            target_document_id=target.id,
            target_content_hash=target.content_hash,
            previous_document_id=(
                previous_current.id
                if previous_current and previous_current.id != target.id
                else None
            ),
        )
        logger.info("Switched current document version id={}", target.id)
        category_name = await repo.get_category_name(getattr(target, "category_id", None))
        return self._to_response(target, category_name=category_name)

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
