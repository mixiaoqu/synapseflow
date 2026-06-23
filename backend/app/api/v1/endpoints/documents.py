"""Document management API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles, require_review_roles
from app.application.document_service import document_service
from app.application.document_upload_service import document_upload_service
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.document import (
    BatchDocumentActionRequest,
    BatchDocumentActionResponse,
    BatchDocumentFilterRequest,
    DocumentChunksResponse,
    DocumentContentUpdate,
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadAbortRequest,
    DocumentUploadActionResponse,
    DocumentUploadCompleteRequest,
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
    DocumentVersionsResponse,
    IndexingPanelSummaryResponse,
)

router = APIRouter()


@router.post("", response_model=DocumentResponse)
async def upload_document(
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
    current_user: User = Depends(require_content_roles),  # noqa: ARG001
):
    raise HTTPException(
        status_code=410,
        detail="Local multipart upload has been removed. Use /documents/uploads/init and /documents/uploads/complete.",
    )


@router.post("/batch", response_model=list[DocumentResponse])
async def upload_documents_batch(
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
    current_user: User = Depends(require_content_roles),  # noqa: ARG001
):
    raise HTTPException(
        status_code=410,
        detail="Local multipart upload has been removed. Use /documents/uploads/init and /documents/uploads/complete.",
    )


@router.post("/uploads/init", response_model=DocumentUploadInitResponse)
async def init_document_upload(
    body: DocumentUploadInitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_upload_service.init_upload(
        db=db,
        user_id=current_user.id,
        body=body,
    )


@router.post("/uploads/complete", response_model=DocumentResponse)
async def complete_document_upload(
    body: DocumentUploadCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_upload_service.complete_upload(
        db=db,
        user_id=current_user.id,
        body=body,
    )


@router.post("/uploads/abort", response_model=DocumentUploadActionResponse)
async def abort_document_upload(
    body: DocumentUploadAbortRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_upload_service.abort_upload(
        db=db,
        user_id=current_user.id,
        body=body,
    )


@router.post("/from-content", response_model=DocumentResponse)
async def create_document_from_content(
    body: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.create_document_from_content(
        db=db,
        user_id=current_user.id,
        body=body,
    )


@router.get("/indexing/panel-summary", response_model=IndexingPanelSummaryResponse)
async def get_indexing_panel_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.get_indexing_panel_summary(
        db=db,
        user_id=current_user.id,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    team_id: int | None = Query(None, description="Filter by team id"),
    knowledge_base_id: int | None = Query(None, description="Filter by knowledge base"),
    category_id: int | None = Query(None, description="Filter by category"),
    status: str | None = Query(None, description="Filter by lifecycle status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.list_documents(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        keyword=keyword,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        status=status,
    )


@router.get("/{doc_id}/versions", response_model=DocumentVersionsResponse)
async def get_document_versions(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.get_document_versions(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )


@router.get("/detail/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.get_document(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )


@router.get("/{doc_id}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.get_document_chunks(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )


@router.post("/reindex-all")
async def reindex_all_documents(
    team_id: int | None = Query(None, description="Reindex documents for team id"),
    knowledge_base_id: int | None = Query(
        None,
        description="Reindex documents for knowledge base id",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.reindex_all_documents(
        db=db,
        user_id=current_user.id,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
    )


@router.post("/{doc_id}/index")
async def index_single_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.index_single_document(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )


@router.put("/{doc_id}/content", response_model=DocumentResponse)
async def replace_document_content(
    doc_id: int,
    body: DocumentContentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.replace_document_content(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
        body=body,
    )


@router.post("/{doc_id}/versions", response_model=DocumentResponse)
async def create_document_version(
    doc_id: int,
    body: DocumentContentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.create_document_version(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
        body=body,
    )


@router.post("/{doc_id}/current", response_model=DocumentResponse)
async def switch_current_document_version(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.switch_current_document_version(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )


@router.delete("/batch/delete")
async def delete_documents_batch(
    ids: list[int] = Query(..., description="Document ids to delete"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.delete_documents_batch(
        db=db,
        user_id=current_user.id,
        ids=ids,
    )


@router.post("/batch/submit-for-review-by-filter", response_model=BatchDocumentActionResponse)
async def submit_documents_for_review_by_filter(
    body: BatchDocumentFilterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.submit_documents_for_review_by_filter(
        db=db,
        user_id=current_user.id,
        filter_body=body,
    )


@router.post("/batch/publish-by-filter", response_model=BatchDocumentActionResponse)
async def publish_documents_by_filter(
    body: BatchDocumentFilterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    return await document_service.publish_documents_by_filter(
        db=db,
        user_id=current_user.id,
        filter_body=body,
    )


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.delete_document(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )


@router.post("/batch/submit-for-review", response_model=BatchDocumentActionResponse)
async def submit_documents_for_review_batch(
    body: BatchDocumentActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.submit_documents_for_review_batch(
        db=db,
        user_id=current_user.id,
        ids=body.ids,
    )


@router.post("/{doc_id}/submit-for-review", response_model=DocumentResponse)
async def submit_document_for_review(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await document_service.submit_document_for_review(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )


@router.post("/batch/reject", response_model=BatchDocumentActionResponse)
async def reject_documents_batch(
    body: BatchDocumentActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    return await document_service.reject_documents_batch(
        db=db,
        user_id=current_user.id,
        ids=body.ids,
    )


@router.post("/{doc_id}/reject", response_model=DocumentResponse)
async def reject_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    return await document_service.reject_document(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )


@router.post("/batch/publish", response_model=BatchDocumentActionResponse)
async def publish_documents_batch(
    body: BatchDocumentActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    return await document_service.publish_documents_batch(
        db=db,
        user_id=current_user.id,
        ids=body.ids,
    )


@router.post("/{doc_id}/publish", response_model=DocumentResponse)
async def publish_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    return await document_service.publish_document(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )


@router.post("/batch/unpublish", response_model=BatchDocumentActionResponse)
async def unpublish_documents_batch(
    body: BatchDocumentActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    return await document_service.unpublish_documents_batch(
        db=db,
        user_id=current_user.id,
        ids=body.ids,
    )


@router.post("/{doc_id}/unpublish", response_model=DocumentResponse)
async def unpublish_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_review_roles),
):
    return await document_service.unpublish_document(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )
