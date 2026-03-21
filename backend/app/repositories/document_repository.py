"""
文档数据访问层
将 SQL 查询封装为 Repository 方法，API 端点仅做编排
"""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, Collection
from app.core.constants import DEFAULT_USER_ID


def _get_root_ids(docs: list) -> set[int]:
    """从文档列表提取去重后的 root_id"""
    return {getattr(d, "root_id", None) or d.id for d in docs}


class DocumentRepository:
    """文档 Repository"""

    def __init__(self, db: AsyncSession, user_id: int = DEFAULT_USER_ID):
        self.db = db
        self.user_id = user_id

    async def create(
        self,
        *,
        title: str,
        content: str,
        document_type: str | None = None,
        size: int = 0,
        collection_id: int | None = None,
    ) -> Document:
        """创建文档"""
        doc = Document(
            user_id=self.user_id,
            title=title,
            content=content,
            document_type=document_type,
            size=size,
            version=1,
            parent_id=None,
            is_latest=True,
            collection_id=collection_id,
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        doc.root_id = doc.id
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def add_for_batch(self, doc: Document) -> None:
        """批量创建时添加文档（不单独 commit）"""
        self.db.add(doc)

    async def commit_and_refresh_root_ids(self, docs: list[Document]) -> None:
        """批量创建后设置 root_id"""
        await self.db.commit()
        for d in docs:
            await self.db.refresh(d)
            d.root_id = d.id
        await self.db.commit()
        for d in docs:
            await self.db.refresh(d)

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        collection_id: int | None = None,
    ) -> tuple[list[tuple[Document, str | None]], int]:
        """
        分页列表，返回 (rows, total)
        rows: [(Document, collection_name), ...]
        """
        base_filter = Document.user_id == self.user_id
        base_filter = base_filter & Document.is_latest.is_(True)
        if keyword and keyword.strip():
            base_filter = base_filter & Document.title.ilike(f"%{keyword.strip()}%")
        if collection_id is not None:
            if collection_id == 0:
                base_filter = base_filter & Document.collection_id.is_(None)
            else:
                base_filter = base_filter & (Document.collection_id == collection_id)

        count_query = select(func.count()).select_from(Document).where(base_filter)
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(Document, Collection.name.label("collection_name"))
            .outerjoin(Collection, Document.collection_id == Collection.id)
            .where(base_filter)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.all()), total

    async def get_by_id(self, doc_id: int) -> Document | None:
        """按 ID 获取（不做 user 校验）"""
        r = await self.db.execute(select(Document).where(Document.id == doc_id))
        return r.scalar_one_or_none()

    async def get_by_id_for_user(self, doc_id: int) -> Document | None:
        """按 ID 获取，校验 user_id"""
        r = await self.db.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.user_id == self.user_id,
            )
        )
        return r.scalar_one_or_none()

    async def get_versions_by_doc_id(self, doc_id: int) -> list[Document]:
        """获取文档版本链（需先确认 doc 存在）"""
        doc = await self.get_by_id(doc_id)
        if not doc:
            return []
        root_id = getattr(doc, "root_id", None) or doc.id
        stmt = (
            select(Document)
            .where(Document.root_id == root_id, Document.user_id == self.user_id)
            .order_by(Document.version.asc())
        )
        r = await self.db.execute(stmt)
        return list(r.scalars().all())

    async def update_content(self, doc_id: int, content: str) -> Document | None:
        """替换文档内容"""
        doc = await self.get_by_id_for_user(doc_id)
        if not doc:
            return None
        doc.content = content
        doc.size = len(content.encode("utf-8"))
        doc.version = (doc.version or 1) + 1
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def create_version(self, doc_id: int, content: str) -> Document | None:
        """创建新版本"""
        orig = await self.get_by_id_for_user(doc_id)
        if not orig:
            return None
        root_id = orig.root_id or orig.id
        max_stmt = select(Document.version).where(
            Document.root_id == root_id,
            Document.is_latest.is_(True),
        )
        max_res = await self.db.execute(max_stmt)
        max_version = max_res.scalar_one_or_none()
        new_version = (max_version or 1) + 1
        size = len(content.encode("utf-8"))
        new_doc = Document(
            user_id=self.user_id,
            title=orig.title,
            content=content,
            document_type=orig.document_type,
            size=size,
            version=new_version,
            parent_id=orig.id,
            root_id=root_id,
            is_latest=True,
            collection_id=getattr(orig, "collection_id", None),
        )
        orig.is_latest = False
        self.db.add(new_doc)
        await self.db.commit()
        await self.db.refresh(new_doc)
        return new_doc

    async def get_by_ids(self, ids: list[int]) -> list[Document]:
        """按 ID 列表获取（仅当前 user）"""
        if not ids:
            return []
        r = await self.db.execute(
            select(Document).where(
                Document.id.in_(ids),
                Document.user_id == self.user_id,
            )
        )
        return list(r.scalars().all())

    async def get_chain_by_root_ids(self, root_ids: set[int]) -> list[Document]:
        """按 root_id 获取整条版本链"""
        if not root_ids:
            return []
        r = await self.db.execute(
            select(Document).where(
                Document.root_id.in_(root_ids),
                Document.user_id == self.user_id,
            )
        )
        return list(r.scalars().all())

    async def delete_chain(self, docs: list[Document]) -> int:
        """删除整条版本链"""
        for d in docs:
            await self.db.delete(d)
        await self.db.commit()
        return len(docs)

    async def count_total(self) -> int:
        """文档总数（用于 404 提示）"""
        r = await self.db.execute(select(func.count()).select_from(Document))
        return r.scalar() or 0
