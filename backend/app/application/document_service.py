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
from app.services.document_indexer import (
    index_document,
    index_documents_batch,
    reindex_all,
)
from app.services.vector_store import delete_by_document_id
from app.utils.file_parser import (
    MAX_FILE_SIZE,
    SUPPORTED_EXTENSIONS,
    extract_text_from_file,
)


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
            raise HTTPException(
                status_code=400,
                detail=f"文件“{filename}”内容为空",
            )
        title, doc_type = self._get_title_and_type(filename)
        return title or "未命名文档", doc_type or None, text

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
            collection_id=getattr(doc, "collection_id", None),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    async def upload_document(
        self,
        *,
        db: AsyncSession,
        file: UploadFile,
        collection_id: int | None,
    ) -> DocumentResponse:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="文件超过 10MB 限制")

        title, doc_type, text = self._parse_single_file(file, content)
        repo = DocumentRepository(db)
        doc = await repo.create(
            title=title,
            content=text,
            document_type=doc_type,
            size=len(text.encode("utf-8")),
            collection_id=collection_id,
            commit=False,
        )

        try:
            await index_document(db, doc.id, doc.content, commit=True)
        except Exception as exc:
            await db.commit()
            logger.warning("文档索引失败 doc_id={}: {}", doc.id, exc)

        await db.refresh(doc)
        logger.info("文档上传成功 id={} title={}", doc.id, doc.title)
        return self._to_response(doc)

    async def upload_documents_batch(
        self,
        *,
        db: AsyncSession,
        files: Sequence[UploadFile],
        collection_id: int | None,
    ) -> list[DocumentResponse]:
        if len(files) > 20:
            raise HTTPException(status_code=400, detail="单次最多上传 20 个文件")

        repo = DocumentRepository(db)
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
                    collection_id=collection_id,
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
            logger.warning("批量文档索引失败 count={}: {}", len(created), exc)

        for doc in created:
            await db.refresh(doc)
        return [self._to_response(doc) for doc in created]

    async def create_document_from_content(
        self,
        *,
        db: AsyncSession,
        body: DocumentCreate,
    ) -> DocumentResponse:
        if not body.content.strip():
            raise HTTPException(status_code=400, detail="文档内容不能为空")

        repo = DocumentRepository(db)
        doc = await repo.create(
            title=(body.title or "").strip() or "未命名文档",
            content=body.content,
            document_type=body.document_type or "txt",
            size=len(body.content.encode("utf-8")),
            collection_id=body.collection_id,
            commit=False,
        )
        try:
            await index_document(db, doc.id, doc.content, commit=True)
        except Exception as exc:
            await db.commit()
            logger.warning("文档索引失败 doc_id={}: {}", doc.id, exc)

        await db.refresh(doc)
        logger.info("从内容创建文档 id={} title={}", doc.id, doc.title)
        return self._to_response(doc)

    async def list_documents(
        self,
        *,
        db: AsyncSession,
        page: int,
        page_size: int,
        keyword: str | None,
        collection_id: int | None,
    ) -> DocumentListResponse:
        page = max(page, 1)
        page_size = 20 if page_size < 1 or page_size > 100 else page_size

        repo = DocumentRepository(db)
        rows, total = await repo.list_paginated(
            page=page,
            page_size=page_size,
            keyword=keyword,
            collection_id=collection_id,
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
                collection_id=getattr(doc, "collection_id", None),
                collection_name=collection_name,
            )
            for doc, collection_name in rows
        ]
        return DocumentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_document_versions(
        self,
        *,
        db: AsyncSession,
        doc_id: int,
    ) -> DocumentVersionsResponse:
        repo = DocumentRepository(db)
        doc = await repo.get_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

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
        doc_id: int,
    ) -> DocumentResponse:
        repo = DocumentRepository(db)
        doc = await repo.get_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        return self._to_response(doc)

    async def reindex_all_documents(self) -> dict[str, int | str]:
        try:
            count = await reindex_all()
            logger.info("全量重建索引完成，共 {} 篇文档", count)
            return {"message": f"已重建索引 {count} 篇文档", "indexed": count}
        except Exception as exc:
            logger.exception("全量重建索引失败: {}", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    async def index_single_document(
        self,
        *,
        db: AsyncSession,
        doc_id: int,
    ) -> dict[str, int | str]:
        repo = DocumentRepository(db)
        doc = await repo.get_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        try:
            count = await index_document(db, doc.id, doc.content or "", commit=True)
            return {"message": f"已索引 {count} 个分块", "chunks": count}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    async def replace_document_content(
        self,
        *,
        db: AsyncSession,
        doc_id: int,
        body: DocumentContentUpdate,
    ) -> DocumentResponse:
        repo = DocumentRepository(db)
        doc = await repo.update_content(doc_id, body.content)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        try:
            await index_document(db, doc.id, doc.content, commit=True)
        except Exception as exc:
            logger.warning("文档索引失败 doc_id={}: {}", doc.id, exc)
        logger.info("文档内容已替换 id={}", doc_id)
        return self._to_response(doc)

    async def create_document_version(
        self,
        *,
        db: AsyncSession,
        doc_id: int,
        body: DocumentContentUpdate,
    ) -> DocumentResponse:
        repo = DocumentRepository(db)
        orig = await repo.get_by_id_for_user(doc_id)
        if not orig:
            raise HTTPException(status_code=404, detail="原文档不存在")

        new_doc = await repo.create_version(doc_id, body.content, commit=False)
        if not new_doc:
            raise HTTPException(status_code=404, detail="原文档不存在")

        try:
            await delete_by_document_id(db, orig.id, commit=False)
            await index_document(db, new_doc.id, new_doc.content, commit=True)
        except Exception as exc:
            await db.commit()
            logger.warning("文档索引失败 doc_id={}: {}", new_doc.id, exc)

        await db.refresh(new_doc)
        logger.info("新建修订版本文档 id={} 源于 doc_id={}", new_doc.id, doc_id)
        return self._to_response(new_doc)

    async def delete_documents_batch(
        self,
        *,
        db: AsyncSession,
        ids: list[int],
    ) -> dict[str, int | str]:
        if not ids:
            return {"message": "未选择文档", "deleted": 0}

        repo = DocumentRepository(db)
        docs = await repo.get_by_ids(ids)
        root_ids = {getattr(doc, "root_id", None) or doc.id for doc in docs}
        chain_docs = await repo.get_chain_by_root_ids(root_ids)
        deleted = await repo.delete_chain(chain_docs)
        logger.info("批量删除文档 ids={}，实际删除 {} 篇", ids, deleted)
        return {"message": f"已删除 {deleted} 篇文档", "deleted": deleted}

    async def delete_document(
        self,
        *,
        db: AsyncSession,
        doc_id: int,
    ) -> dict[str, str]:
        repo = DocumentRepository(db)
        doc = await repo.get_by_id_for_user(doc_id)
        if not doc:
            count = await repo.count_total()
            raise HTTPException(
                status_code=404,
                detail=f"文档不存在 id={doc_id}, 当前库中共 {count} 篇",
            )

        root_id = getattr(doc, "root_id", None) or doc.id
        chain_docs = await repo.get_chain_by_root_ids({root_id})
        await repo.delete_chain(chain_docs)
        logger.info("删除文档 id={} 及同链 {} 个版本", doc_id, len(chain_docs))
        return {"message": "删除成功"}


document_service = DocumentService()
