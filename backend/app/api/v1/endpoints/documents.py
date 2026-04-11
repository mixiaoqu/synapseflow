"""Document management API."""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.application.document_service import document_service
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.document import (
    DocumentContentUpdate,
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentVersionsResponse,
)

router = APIRouter()


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(..., description="Document file"),
    knowledge_base_id: int | None = Form(None, description="Owning knowledge base id"),
    category_id: int | None = Form(None, description="Owning category id"),
    source_path: str | None = Form(None, description="Original relative source path"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await document_service.upload_document(
        db=db,
        user_id=current_user.id,
        file=file,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        source_path=source_path,
    )


@router.post("/batch", response_model=list[DocumentResponse])
async def upload_documents_batch(
    files: list[UploadFile] = File(..., description="Document files"),
    knowledge_base_id: int | None = Form(None, description="Owning knowledge base id"),
    category_id: int | None = Form(None, description="Owning category id"),
    source_paths: list[str] | None = Form(
        None,
        description="Relative source paths aligned with files order",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await document_service.upload_documents_batch(
        db=db,
        user_id=current_user.id,
        files=files,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        source_paths=source_paths,
    )


@router.post("/from-content", response_model=DocumentResponse)
async def create_document_from_content(
    body: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await document_service.create_document_from_content(
        db=db,
        user_id=current_user.id,
        body=body,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    team_id: int | None = Query(None, description="Filter by team id"),
    knowledge_base_id: int | None = Query(None, description="Filter by knowledge base"),
    category_id: int | None = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    )


@router.get("/{doc_id}/versions", response_model=DocumentVersionsResponse)
async def get_document_versions(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
):
    return await document_service.get_document(
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
):
    return await document_service.delete_documents_batch(
        db=db,
        user_id=current_user.id,
        ids=ids,
    )


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await document_service.delete_document(
        db=db,
        user_id=current_user.id,
        doc_id=doc_id,
    )
