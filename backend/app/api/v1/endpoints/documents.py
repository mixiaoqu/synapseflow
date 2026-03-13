"""
文档管理 API
支持上传、列表、详情、删除、搜索、批量上传、批量删除
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Document
from app.services.document_indexer import index_document, reindex_all
from app.models.schemas.document import (
    DocumentResponse,
    DocumentListItem,
    DocumentListResponse,
)
from app.core.file_parser import extract_text_from_file

router = APIRouter()

DEFAULT_USER_ID = 1

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# 注意：DELETE /batch-delete 必须定义在 DELETE /{doc_id} 之前，否则 "batch-delete" 会被当作 doc_id


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


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(..., description="文档文件"),
    db: AsyncSession = Depends(get_db),
):
    """
    上传文档入库
    支持格式：.txt, .md, .pdf, .docx，最大 10MB
    """
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 10MB 限制")
    title, doc_type, text = _parse_single_file(file, content)

    size = len(text.encode("utf-8"))
    doc = Document(
        user_id=DEFAULT_USER_ID,
        title=title,
        content=text,
        document_type=doc_type,
        size=size,
        version=1,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    try:
        await index_document(db, doc.id, doc.content)
    except Exception:
        pass  # 索引失败不阻塞上传，可通过重索引 API 修复
    return doc


@router.post("/batch", response_model=list[DocumentResponse])
async def upload_documents_batch(
    files: list[UploadFile] = File(..., description="多个文档文件"),
    db: AsyncSession = Depends(get_db),
):
    """
    批量上传文档
    支持格式：.txt, .md, .pdf, .docx，每个最大 10MB
    """
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="单次最多上传 20 个文件")
    created = []
    for f in files:
        try:
            content = await f.read()
            if len(content) > MAX_FILE_SIZE:
                continue  # 跳过超限文件
            ext = "." + (f.filename or "").rsplit(".", 1)[-1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            title, doc_type, text = _parse_single_file(f, content)
            size = len(text.encode("utf-8"))
            doc = Document(
                user_id=DEFAULT_USER_ID,
                title=title,
                content=text,
                document_type=doc_type,
                size=size,
                version=1,
            )
            db.add(doc)
            created.append(doc)
        except HTTPException:
            raise
        except Exception:
            pass  # 跳过失败文件
    await db.commit()
    for d in created:
        await db.refresh(d)
        try:
            await index_document(db, d.id, d.content)
        except Exception:
            pass
    return created


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """分页获取文档列表，支持关键词搜索"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    base_filter = Document.user_id == DEFAULT_USER_ID
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        base_filter = base_filter & (
            Document.title.ilike(kw) | Document.content.ilike(kw)
        )

    count_query = select(func.count()).select_from(Document).where(base_filter)
    total = (await db.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    query = (
        select(Document)
        .where(base_filter)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    docs = result.scalars().all()

    items = [
        DocumentListItem(
            id=d.id,
            title=d.title,
            document_type=d.document_type,
            size=getattr(d, "size", 0) or len((d.content or "").encode("utf-8")),
            version=getattr(d, "version", 1),
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in docs
    ]
    return DocumentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/detail/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个文档详情（含 content）"""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        # 调试：若经常 404，可取消下行注释查看库中实际 id
        # all_ids = (await db.execute(select(Document.id))).scalars().all()
        # print(f"[documents] 请求 id={doc_id}，库中存在的 id: {all_ids}")
        raise HTTPException(status_code=404, detail="文档不存在")
    size = getattr(doc, "size", 0) or len((doc.content or "").encode("utf-8"))
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        content=doc.content or "",
        document_type=doc.document_type,
        size=size,
        version=getattr(doc, "version", 1),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("/reindex-all")
async def reindex_all_documents(db: AsyncSession = Depends(get_db)):
    """全量重索引：对所有文档重新建立向量索引"""
    try:
        count = await reindex_all()
        return {"message": f"已重索引 {count} 篇文档", "indexed": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{doc_id}/index")
async def index_single_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    """对单篇文档建立或重建向量索引"""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        count = await index_document(db, doc.id, doc.content or "")
        return {"message": f"已索引 {count} 个分块", "chunks": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/batch/delete")
async def delete_documents_batch(
    ids: list[int] = Query(..., description="要删除的文档ID列表"),
    db: AsyncSession = Depends(get_db),
):
    """批量删除文档"""
    if not ids:
        return {"message": "未选择文档", "deleted": 0}
    result = await db.execute(
        select(Document).where(
            Document.id.in_(ids),
            Document.user_id == DEFAULT_USER_ID,
        )
    )
    docs = result.scalars().all()
    for d in docs:
        await db.delete(d)
    await db.commit()
    return {"message": f"已删除 {len(docs)} 篇文档", "deleted": len(docs)}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除文档"""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == DEFAULT_USER_ID)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        cnt = (await db.execute(select(func.count()).select_from(Document))).scalar() or 0
        raise HTTPException(status_code=404, detail=f"文档不存在(id={doc_id}, 当前库中共{cnt}篇)")
    await db.delete(doc)
    await db.commit()
    return {"message": "删除成功"}
