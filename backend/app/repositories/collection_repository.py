"""
集合数据访问层
"""
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Collection, Document
from app.core.constants import DEFAULT_USER_ID


class CollectionRepository:
    """集合 Repository"""

    def __init__(self, db: AsyncSession, user_id: int = DEFAULT_USER_ID):
        self.db = db
        self.user_id = user_id

    async def list_with_count(self) -> list[tuple[Collection, int]]:
        """获取所有集合及文档数"""
        stmt = (
            select(Collection, func.count(Document.id).label("doc_count"))
            .outerjoin(
                Document,
                (Document.collection_id == Collection.id)
                & (Document.is_latest.is_(True)),
            )
            .where(Collection.user_id == self.user_id)
            .group_by(Collection.id)
            .order_by(Collection.created_at.desc())
        )
        r = await self.db.execute(stmt)
        return [(c, doc_count or 0) for c, doc_count in r.all()]

    async def create(self, name: str) -> Collection:
        """创建集合"""
        col = Collection(user_id=self.user_id, name=name.strip())
        self.db.add(col)
        await self.db.commit()
        await self.db.refresh(col)
        return col

    async def get_by_id(self, collection_id: int) -> Collection | None:
        """按 ID 获取"""
        r = await self.db.execute(
            select(Collection).where(
                Collection.id == collection_id,
                Collection.user_id == self.user_id,
            )
        )
        return r.scalar_one_or_none()

    async def update_name(self, collection_id: int, name: str) -> Collection | None:
        """更新集合名称"""
        col = await self.get_by_id(collection_id)
        if not col:
            return None
        col.name = name.strip()
        await self.db.commit()
        await self.db.refresh(col)
        return col

    async def delete(self, collection_id: int) -> bool:
        """
        删除集合，将关联文档的 collection_id 置为 NULL。
        返回是否找到并删除。
        """
        col = await self.get_by_id(collection_id)
        if not col:
            return False
        await self.db.execute(
            update(Document)
            .where(Document.collection_id == collection_id)
            .values(collection_id=None)
        )
        await self.db.delete(col)
        await self.db.commit()
        return True
