"""文档管理 API。"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import document_service
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
    file: UploadFile = File(..., description="文档文件"),
    collection_id: int | None = Form(None, description="所属集合 ID"),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.upload_document(
        db=db,
        file=file,
        collection_id=collection_id,
    )


@router.post("/batch", response_model=list[DocumentResponse])
async def upload_documents_batch(
    files: list[UploadFile] = File(..., description="多个文档文件"),
    collection_id: int | None = Form(None, description="所属集合 ID"),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.upload_documents_batch(
        db=db,
        files=files,
        collection_id=collection_id,
    )


@router.post("/from-content", response_model=DocumentResponse)
async def create_document_from_content(
    body: DocumentCreate,
    db: AsyncSession = Depends(get_db),
):
    return await document_service.create_document_from_content(db=db, body=body)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    collection_id: int | None = Query(None, description="按集合筛选"),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(
        db=db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        collection_id=collection_id,
    )


@router.get("/{doc_id}/versions", response_model=DocumentVersionsResponse)
async def get_document_versions(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await document_service.get_document_versions(db=db, doc_id=doc_id)


@router.get("/detail/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await document_service.get_document(db=db, doc_id=doc_id)


@router.post("/reindex-all")
async def reindex_all_documents():
    return await document_service.reindex_all_documents()


@router.post("/{doc_id}/index")
async def index_single_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await document_service.index_single_document(db=db, doc_id=doc_id)


@router.put("/{doc_id}/content", response_model=DocumentResponse)
async def replace_document_content(
    doc_id: int,
    body: DocumentContentUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await document_service.replace_document_content(
        db=db,
        doc_id=doc_id,
        body=body,
    )


@router.post("/{doc_id}/versions", response_model=DocumentResponse)
async def create_document_version(
    doc_id: int,
    body: DocumentContentUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await document_service.create_document_version(
        db=db,
        doc_id=doc_id,
        body=body,
    )


@router.delete("/batch/delete")
async def delete_documents_batch(
    ids: list[int] = Query(..., description="要删除的文档 ID 列表"),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.delete_documents_batch(db=db, ids=ids)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await document_service.delete_document(db=db, doc_id=doc_id)
