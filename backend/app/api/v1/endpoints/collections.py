"""集合管理 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.schemas.collection import (
    CollectionCreate,
    CollectionResponse,
    CollectionUpdate,
    CollectionWithCount,
)
from app.repositories.collection_repository import CollectionRepository

router = APIRouter()


@router.get("", response_model=list[CollectionWithCount])
async def list_collections(db: AsyncSession = Depends(get_db)):
    """获取所有集合及每个集合的文档数量。"""
    repo = CollectionRepository(db)
    rows = await repo.list_with_count()
    return [
        CollectionWithCount(
            id=collection.id,
            name=collection.name,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
            document_count=doc_count,
        )
        for collection, doc_count in rows
    ]


@router.post("", response_model=CollectionResponse)
async def create_collection(
    body: CollectionCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建集合。"""
    repo = CollectionRepository(db)
    return await repo.create(body.name)


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: int,
    body: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新集合名称。"""
    repo = CollectionRepository(db)
    collection = await repo.update_name(collection_id, body.name)
    if not collection:
        raise HTTPException(status_code=404, detail="集合不存在")
    return collection


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除集合。"""
    repo = CollectionRepository(db)
    ok = await repo.delete(collection_id)
    if not ok:
        raise HTTPException(status_code=404, detail="集合不存在")
    return {"message": "删除成功"}
