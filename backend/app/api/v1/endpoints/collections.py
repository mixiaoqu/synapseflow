"""集合管理 API"""
from fastapi import APIRouter, HTTPException, Depends

from app.db.session import get_db
from app.repositories.collection_repository import CollectionRepository
from app.models.schemas.collection import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionWithCount,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[CollectionWithCount])
async def list_collections(db: AsyncSession = Depends(get_db)):
    """获取所有集合及每个集合的文档数"""
    repo = CollectionRepository(db)
    rows = await repo.list_with_count()
    return [
        CollectionWithCount(
            id=c.id,
            name=c.name,
            created_at=c.created_at,
            updated_at=c.updated_at,
            document_count=doc_count,
        )
        for c, doc_count in rows
    ]


@router.post("", response_model=CollectionResponse)
async def create_collection(
    body: CollectionCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建集合"""
    repo = CollectionRepository(db)
    col = await repo.create(body.name)
    return col


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: int,
    body: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新集合名称"""
    repo = CollectionRepository(db)
    col = await repo.update_name(collection_id, body.name)
    if not col:
        raise HTTPException(status_code=404, detail="集合不存在")
    return col


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除集合"""
    repo = CollectionRepository(db)
    ok = await repo.delete(collection_id)
    if not ok:
        raise HTTPException(status_code=404, detail="集合不存在")
    return {"message": "删除成功"}
