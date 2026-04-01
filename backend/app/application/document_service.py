"""Application service for document management orchestration."""

from __future__ import annotations

from typing import Sequence

from fastapi import HTTPException, UploadFile
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.repositories.document_repository import DocumentRepository
from app.services.document_indexer import index_document, index_documents_batch, reindex_all
from app.services.vector_store import delete_by_document_id
from app.utils.file_parser import MAX_FILE_SIZE, SUPPORTED_EXTENSIONS, extract_text_from_file


class DocumentService:
    """Coordinates document CRUD, versioning, and indexing workflows."""

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

    def _to_response(self, doc: Document) -> DocumentResponse:
        return DocumentResponse(
            id=doc.id,
            title=doc.title,
            content=doc.content or "",
            document_type=doc.document_type,
            size=self._document_size(doc),
            version=getattr(doc, "version", 1),
            knowledge_base_id=getattr(doc, "knowledge_base_id", None),
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
    ) -> DocumentResponse:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File exceeds the 10MB limit")

        title, doc_type, text = self._parse_single_file(file, content)
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.create(
            title=title,
            content=text,
            document_type=doc_type,
            size=len(text.encode("utf-8")),
            knowledge_base_id=knowledge_base_id,
            commit=False,
        )

        try:
            await index_document(db, doc.id, doc.content, commit=True)
        except Exception as exc:
            await db.commit()
            logger.warning("Document indexing failed doc_id={}: {}", doc.id, exc)

        await db.refresh(doc)
        logger.info("Uploaded document id={} title={}", doc.id, doc.title)
        return self._to_response(doc)

    async def upload_documents_batch(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        files: Sequence[UploadFile],
        knowledge_base_id: int | None,
    ) -> list[DocumentResponse]:
        if len(files) > 20:
            raise HTTPException(status_code=400, detail="At most 20 files can be uploaded at once")

        repo = DocumentRepository(db, user_id=user_id)
        created: list[Document] = []

        for file in files:
            try:
                content = await file.read()
                if len(content) > MAX_FILE_SIZE:
                    continue
                ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                title, doc_type, text = self._parse_single_file(file, content)
                doc = Document(
                    user_id=repo.user_id,
                    title=title,
                    content=text,
                    document_type=doc_type,
                    size=len(text.encode("utf-8")),
                    version=1,
                    parent_id=None,
                    is_latest=True,
                    knowledge_base_id=knowledge_base_id,
                )
                await repo.add_for_batch(doc)
                created.append(doc)
            except HTTPException:
                raise
            except Exception:
                continue

        await repo.prepare_batch_create(created)
        try:
            await index_documents_batch(
                db,
                [(doc.id, doc.content or "") for doc in created],
                commit=True,
            )
        except Exception as exc:
            await db.commit()
            logger.warning("Batch document indexing failed count={}: {}", len(created), exc)

        for doc in created:
            await db.refresh(doc)
        return [self._to_response(doc) for doc in created]

    async def create_document_from_content(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        body: DocumentCreate,
    ) -> DocumentResponse:
        if not body.content.strip():
            raise HTTPException(status_code=400, detail="Document content cannot be empty")

        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.create(
            title=(body.title or "").strip() or "Untitled document",
            content=body.content,
            document_type=body.document_type or "txt",
            size=len(body.content.encode("utf-8")),
            knowledge_base_id=body.knowledge_base_id,
            commit=False,
        )
        try:
            await index_document(db, doc.id, doc.content, commit=True)
        except Exception as exc:
            await db.commit()
            logger.warning("Document indexing failed doc_id={}: {}", doc.id, exc)

        await db.refresh(doc)
        logger.info("Created document from content id={} title={}", doc.id, doc.title)
        return self._to_response(doc)

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
                indexed=getattr(doc, "indexed_at", None) is not None,
                knowledge_base_id=getattr(doc, "knowledge_base_id", None),
                knowledge_base_name=knowledge_base_name,
            )
            for doc, knowledge_base_name in rows
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
        return self._to_response(doc)

    async def reindex_all_documents(
        self,
        *,
        user_id: int,
        team_id: int | None = None,
        knowledge_base_id: int | None = None,
    ) -> dict[str, int | str]:
        try:
            count = await reindex_all(
                user_id=user_id,
                team_id=team_id,
                knowledge_base_id=knowledge_base_id,
            )
            logger.info("Finished full reindex for {} documents", count)
            return {"message": f"Reindexed {count} documents", "indexed": count}
        except Exception as exc:
            logger.exception("Full reindex failed: {}", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    async def index_single_document(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
    ) -> dict[str, int | str]:
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.get_by_id_for_user(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        try:
            count = await index_document(db, doc.id, doc.content or "", commit=True)
            return {"message": f"Indexed {count} chunks", "chunks": count}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    async def replace_document_content(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        doc_id: int,
        body: DocumentContentUpdate,
    ) -> DocumentResponse:
        repo = DocumentRepository(db, user_id=user_id)
        doc = await repo.update_content(doc_id, body.content)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        try:
            await index_document(db, doc.id, doc.content, commit=True)
        except Exception as exc:
            logger.warning("Document indexing failed doc_id={}: {}", doc.id, exc)
        logger.info("Replaced document content id={}", doc_id)
        return self._to_response(doc)

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

        new_doc = await repo.create_version(doc_id, body.content, commit=False)
        if not new_doc:
            raise HTTPException(status_code=404, detail="Source document not found")

        try:
            await delete_by_document_id(db, orig.id, commit=False)
            await index_document(db, new_doc.id, new_doc.content, commit=True)
        except Exception as exc:
            await db.commit()
            logger.warning("Document indexing failed doc_id={}: {}", new_doc.id, exc)

        await db.refresh(new_doc)
        logger.info("Created document version id={} from doc_id={}", new_doc.id, doc_id)
        return self._to_response(new_doc)

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
