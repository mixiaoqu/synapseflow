"""
文档管理 API
支持上传、列表、详情、删除、搜索、批量上传、批量删除
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Document
from app.repositories.document_repository import DocumentRepository
from app.services.document_indexer import index_document, reindex_all
from app.services.vector_store import delete_by_document_id
from app.models.schemas.document import (
    DocumentResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentContentUpdate,
    DocumentCreate,
    DocumentVersionItem,
    DocumentVersionsResponse,
)
from app.utils.file_parser import extract_text_from_file, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE

router = APIRouter()


def _get_title_and_type(filename: str) -> tuple[str, str]:
    """从文件名提取标题（去掉扩展名）和类型"""
    if "." in filename:
        name, ext = filename.rsplit(".", 1)
        return name.strip() or filename, ext.lower()
    return filename, ""


def _parse_single_file(file: UploadFile, content: bytes):
    """解析单个文件并返回 (title, doc_type, text)"""
    filename = file.filename or "unknown"
    text, err = extract_text_from_file(filename, content)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if not text.strip():
        raise HTTPException(status_code=400, detail=f"文件「{filename}」内容为空")
    title, doc_type = _get_title_and_type(filename)
    if not title:
        title = "未命名文档"
    return title, doc_type or None, text


def _to_response(doc: Document) -> DocumentResponse:
    size = getattr(doc, "size", 0) or len((doc.content or "").encode("utf-8"))
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        content=doc.content or "",
        document_type=doc.document_type,
        size=size,
        version=getattr(doc, "version", 1),
        collection_id=getattr(doc, "collection_id", None),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(..., description="文档文件"),
    collection_id: int | None = Form(None, description="所属集合 ID"),
    db: AsyncSession = Depends(get_db),
):
    """上传文档入库，支持格式：.txt, .md, .pdf, .docx，最大 10MB"""
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 10MB 限制")
    title, doc_type, text = _parse_single_file(file, content)

    repo = DocumentRepository(db)
    doc = await repo.create(
        title=title,
        content=text,
        document_type=doc_type,
        size=len(text.encode("utf-8")),
        collection_id=collection_id,
    )
    try:
        await index_document(db, doc.id, doc.content)
    except Exception as e:
        logger.warning("文档索引失败 doc_id={}: {}", doc.id, e)
    logger.info("文档上传成功 id={} title={}", doc.id, doc.title)
    return _to_response(doc)


@router.post("/batch", response_model=list[DocumentResponse])
async def upload_documents_batch(
    files: list[UploadFile] = File(..., description="多个文档文件"),
    collection_id: int | None = Form(None, description="所属集合 ID"),
    db: AsyncSession = Depends(get_db),
):
    """批量上传文档"""
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="单次最多上传 20 个文件")

    repo = DocumentRepository(db)
    created = []
    for f in files:
        try:
            content = await f.read()
            if len(content) > MAX_FILE_SIZE:
                continue
            ext = "." + (f.filename or "").rsplit(".", 1)[-1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            title, doc_type, text = _parse_single_file(f, content)
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
            pass

    await repo.commit_and_refresh_root_ids(created)
    for d in created:
        try:
            await index_document(db, d.id, d.content)
        except Exception:
            pass
    return [_to_response(d) for d in created]


@router.post("/from-content", response_model=DocumentResponse)
async def create_document_from_content(
    body: DocumentCreate,
    db: AsyncSession = Depends(get_db),
):
    """从文本内容创建文档（用于粘贴文档后保存到知识库）"""
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="文档内容不能为空")
    title = (body.title or "").strip() or "未命名文档"
    size = len(body.content.encode("utf-8"))

    repo = DocumentRepository(db)
    doc = await repo.create(
        title=title,
        content=body.content,
        document_type=body.document_type or "txt",
        size=size,
        collection_id=body.collection_id,
    )
    try:
        await index_document(db, doc.id, doc.content)
    except Exception as e:
        logger.warning("文档索引失败 doc_id={}: {}", doc.id, e)
    logger.info("从内容创建文档 id={} title={}", doc.id, doc.title)
    return _to_response(doc)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    collection_id: int | None = Query(None, description="按集合筛选"),
    db: AsyncSession = Depends(get_db),
):
    """分页获取文档列表"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    repo = DocumentRepository(db)
    rows, total = await repo.list_paginated(
        page=page,
        page_size=page_size,
        keyword=keyword,
        collection_id=collection_id,
    )
    items = [
        DocumentListItem(
            id=d.id,
            title=d.title,
            document_type=d.document_type,
            size=getattr(d, "size", 0) or len((d.content or "").encode("utf-8")),
            version=getattr(d, "version", 1),
            created_at=d.created_at,
            updated_at=d.updated_at,
            indexed=getattr(d, "indexed_at", None) is not None,
            collection_id=getattr(d, "collection_id", None),
            collection_name=col_name,
        )
        for d, col_name in rows
    ]
    return DocumentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{doc_id}/versions", response_model=DocumentVersionsResponse)
async def get_document_versions(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取文档版本历史"""
    repo = DocumentRepository(db)
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    vers_docs = await repo.get_versions_by_doc_id(doc_id)
    items = [
        DocumentVersionItem(
            id=d.id,
            title=d.title,
            version=getattr(d, "version", 1),
            is_latest=getattr(d, "is_latest", True),
            created_at=d.created_at,
        )
        for d in vers_docs
    ]
    return DocumentVersionsResponse(items=items)


@router.get("/detail/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个文档详情"""
    repo = DocumentRepository(db)
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return _to_response(doc)


@router.post("/reindex-all")
async def reindex_all_documents(db: AsyncSession = Depends(get_db)):
    """全量重索引"""
    try:
        count = await reindex_all()
        logger.info("全量重索引完成，共 {} 篇文档", count)
        return {"message": f"已重索引 {count} 篇文档", "indexed": count}
    except Exception as e:
        logger.exception("全量重索引失败: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{doc_id}/index")
async def index_single_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    """对单篇文档建立或重建向量索引"""
    repo = DocumentRepository(db)
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        count = await index_document(db, doc.id, doc.content or "")
        return {"message": f"已索引 {count} 个分块", "chunks": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{doc_id}/content", response_model=DocumentResponse)
async def replace_document_content(
    doc_id: int,
    body: DocumentContentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """替换文档内容"""
    repo = DocumentRepository(db)
    doc = await repo.update_content(doc_id, body.content)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        await index_document(db, doc.id, doc.content)
    except Exception as e:
        logger.warning("文档索引失败 doc_id={}: {}", doc.id, e)
    logger.info("文档内容已替换 id={}", doc_id)
    return _to_response(doc)


@router.post("/{doc_id}/versions", response_model=DocumentResponse)
async def create_document_version(
    doc_id: int,
    body: DocumentContentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """作为新版本保存"""
    repo = DocumentRepository(db)
    orig = await repo.get_by_id_for_user(doc_id)
    if not orig:
        raise HTTPException(status_code=404, detail="原文档不存在")

    new_doc = await repo.create_version(doc_id, body.content)
    if not new_doc:
        raise HTTPException(status_code=404, detail="原文档不存在")

    await delete_by_document_id(db, orig.id)
    try:
        await index_document(db, new_doc.id, new_doc.content)
    except Exception as e:
        logger.warning("文档索引失败 doc_id={}: {}", new_doc.id, e)
    logger.info("新建修订版文档 id={} 源于 doc_id={}", new_doc.id, doc_id)
    return _to_response(new_doc)


@router.delete("/batch/delete")
async def delete_documents_batch(
    ids: list[int] = Query(..., description="要删除的文档ID列表"),
    db: AsyncSession = Depends(get_db),
):
    """批量删除文档"""
    if not ids:
        return {"message": "未选择文档", "deleted": 0}
    repo = DocumentRepository(db)
    docs = await repo.get_by_ids(ids)
    root_ids = {getattr(d, "root_id", None) or d.id for d in docs}
    chain_docs = await repo.get_chain_by_root_ids(root_ids)
    deleted = await repo.delete_chain(chain_docs)
    logger.info("批量删除文档 ids={}, 实际删除 {} 篇", ids, deleted)
    return {"message": f"已删除 {deleted} 篇文档", "deleted": deleted}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除文档"""
    repo = DocumentRepository(db)
    doc = await repo.get_by_id_for_user(doc_id)
    if not doc:
        cnt = await repo.count_total()
        raise HTTPException(status_code=404, detail=f"文档不存在(id={doc_id}, 当前库中共{cnt}篇)")
    root_id = getattr(doc, "root_id", None) or doc.id
    chain_docs = await repo.get_chain_by_root_ids({root_id})
    await repo.delete_chain(chain_docs)
    logger.info("删除文档 id={} 及同链 {} 个版本", doc_id, len(chain_docs))
    return {"message": "删除成功"}
