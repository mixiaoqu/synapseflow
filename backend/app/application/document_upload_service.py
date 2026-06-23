"""Application service for direct object-storage document uploads."""

from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.models.schemas.document import (
    DocumentResponse,
    DocumentUploadAbortRequest,
    DocumentUploadActionResponse,
    DocumentUploadCompleteRequest,
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
)
from app.repositories.document_category_repository import DocumentCategoryRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_upload_session_repository import DocumentUploadSessionRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.services.object_storage_service import (
    ObjectStorageAuthorizationError,
    ObjectStorageError,
    ObjectStorageObjectNotFoundError,
    object_storage_service,
)
from app.utils.document_parse import SUPPORTED_EXTENSIONS
from app.utils.time import utc_now


class DocumentUploadService:
    """Coordinate upload-session initialization and completion."""

    @staticmethod
    def _safe_filename(filename: str) -> str:
        normalized = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        return normalized or "document"

    @classmethod
    def _file_extension(cls, filename: str) -> str:
        safe_filename = cls._safe_filename(filename)
        if "." not in safe_filename:
            return ""
        return "." + safe_filename.rsplit(".", 1)[-1].lower()

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
    def _validate_upload_request(cls, body: DocumentUploadInitRequest) -> str:
        if body.file_size <= 0:
            raise HTTPException(status_code=400, detail="File size must be greater than 0")
        if body.file_size > int(settings.MAX_UPLOAD_SIZE):
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds the {int(settings.MAX_UPLOAD_SIZE) // (1024 * 1024)}MB limit",
            )

        safe_filename = cls._safe_filename(body.filename)
        extension = cls._file_extension(safe_filename)
        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="不支持的文件格式: %s，支持 %s"
                % (extension or "无扩展名", ", ".join(sorted(SUPPORTED_EXTENSIONS))),
            )
        return safe_filename

    async def init_upload(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        body: DocumentUploadInitRequest,
    ) -> DocumentUploadInitResponse:
        safe_filename = self._validate_upload_request(body)
        try:
            object_storage_service.ensure_enabled()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        kb_repo = KnowledgeBaseRepository(db, user_id=user_id)
        knowledge_base = await kb_repo.get_by_id(body.knowledge_base_id)
        if knowledge_base is None:
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        category_id = body.category_id
        if category_id is not None:
            category = await DocumentCategoryRepository(db, user_id=user_id).get_by_id(category_id)
            if category is None:
                raise HTTPException(status_code=404, detail="Category not found")
            if int(category.knowledge_base_id) != int(knowledge_base.id):
                raise HTTPException(
                    status_code=400,
                    detail="Category does not belong to the selected knowledge base",
                )

        object_key = object_storage_service.build_document_object_key(
            team_id=int(knowledge_base.team_id),
            knowledge_base_id=int(knowledge_base.id),
            filename=safe_filename,
        )
        upload_policy = object_storage_service.create_browser_upload_policy(
            bucket_name=settings.OSS_BUCKET.strip(),
            object_key=object_key,
            file_size=body.file_size,
            content_type=body.content_type,
        )
        session = await DocumentUploadSessionRepository(db, user_id=user_id).create_session(
            team_id=int(knowledge_base.team_id),
            knowledge_base_id=int(knowledge_base.id),
            category_id=category_id,
            original_filename=safe_filename,
            source_path=self._normalize_source_path(body.source_path),
            bucket_name=upload_policy.bucket_name,
            object_key=upload_policy.object_key,
            file_size=body.file_size,
            content_type=(body.content_type or "").strip() or None,
            expires_at=upload_policy.expires_at,
        )
        return DocumentUploadInitResponse(
            upload_session_id=int(session.id),
            provider=upload_policy.provider,
            method=upload_policy.method,
            bucket_name=upload_policy.bucket_name,
            object_key=upload_policy.object_key,
            upload_url=upload_policy.upload_url,
            expires_at=upload_policy.expires_at,
            form_fields=upload_policy.form_fields,
        )

    async def complete_upload(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        body: DocumentUploadCompleteRequest,
    ) -> DocumentResponse:
        from app.application.document_service import document_service

        repo = DocumentUploadSessionRepository(db, user_id=user_id)
        session = await repo.get_by_id_for_user(body.upload_session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Upload session not found")

        now = utc_now()
        if session.status == "completed":
            existing_doc = (
                await DocumentRepository(db, user_id=user_id).get_by_id_for_user(int(session.document_id))
                if getattr(session, "document_id", None)
                else None
            )
            if existing_doc is None:
                raise HTTPException(
                    status_code=409,
                    detail="Upload session is already completed but no document record is linked",
                )
            category_name = await DocumentRepository(db, user_id=user_id).get_category_name(
                getattr(existing_doc, "category_id", None)
            )
            return document_service.to_response(existing_doc, category_name=category_name)
        if session.status in {"aborted", "expired"}:
            raise HTTPException(status_code=400, detail=f"Upload session is already {session.status}")
        if session.expires_at <= now:
            await repo.mark_expired(session)
            raise HTTPException(status_code=400, detail="Upload session has expired")

        try:
            metadata = await object_storage_service.head_object(
                bucket_name=str(session.bucket_name),
                object_key=str(session.object_key),
            )
        except ObjectStorageObjectNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ObjectStorageAuthorizationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ObjectStorageError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        if metadata.content_length <= 0:
            raise HTTPException(status_code=400, detail="Uploaded object is empty")
        if metadata.content_length != int(session.file_size):
            raise HTTPException(status_code=400, detail="Uploaded object size does not match upload session")

        knowledge_base_id, category_id, source_path = await document_service.resolve_document_location(
            db=db,
            user_id=user_id,
            knowledge_base_id=int(session.knowledge_base_id),
            category_id=getattr(session, "category_id", None),
            source_path=getattr(session, "source_path", None),
        )
        title, document_type = self._get_title_and_type(str(session.original_filename))
        doc_repo = DocumentRepository(db, user_id=user_id)
        doc = await doc_repo.create_uploaded_source_document(
            title=title or "Untitled document",
            document_type=document_type or None,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            source_path=source_path,
            source_storage_provider=settings.OSS_PROVIDER.strip() or "aliyun_oss",
            source_bucket_name=str(session.bucket_name),
            source_object_key=str(session.object_key),
            source_file_name=str(session.original_filename),
            source_file_size=metadata.content_length,
            source_content_type=metadata.content_type or getattr(session, "content_type", None),
            source_etag=metadata.etag,
            commit=False,
        )
        await repo.mark_completed(session, document_id=int(doc.id), commit=False)
        await db.commit()
        await db.refresh(doc)
        await db.refresh(session)
        await document_service.enqueue_document_parse_task(db=db, doc=doc)
        await db.refresh(doc)
        category_name = await doc_repo.get_category_name(category_id)
        return document_service.to_response(doc, category_name=category_name)

    async def abort_upload(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        body: DocumentUploadAbortRequest,
    ) -> DocumentUploadActionResponse:
        repo = DocumentUploadSessionRepository(db, user_id=user_id)
        session = await repo.get_by_id_for_user(body.upload_session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Upload session not found")

        if session.status == "aborted":
            return DocumentUploadActionResponse(
                upload_session_id=int(session.id),
                status="aborted",
                message="Upload session already aborted",
            )
        if session.status == "completed":
            raise HTTPException(status_code=400, detail="Completed upload session cannot be aborted")

        await repo.mark_aborted(session)
        return DocumentUploadActionResponse(
            upload_session_id=int(session.id),
            status="aborted",
            message="Upload session aborted",
        )

    @classmethod
    def _get_title_and_type(cls, filename: str) -> tuple[str, str]:
        safe_filename = cls._safe_filename(filename)
        if "." in safe_filename:
            title, extension = safe_filename.rsplit(".", 1)
            return title.strip() or safe_filename, extension.lower()
        return safe_filename, ""


document_upload_service = DocumentUploadService()
