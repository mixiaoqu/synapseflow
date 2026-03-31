"""Document repository helpers."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_USER_ID
from app.db.models import Collection, Document


class DocumentRepository:
    """Encapsulates document persistence operations."""

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
        commit: bool = True,
    ) -> Document:
        """Create a document row and set its root_id in the same transaction."""
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
        await self.db.flush()
        doc.root_id = doc.id
        if commit:
            await self.db.commit()
            await self.db.refresh(doc)
        return doc

    async def add_for_batch(self, doc: Document) -> None:
        """Queue a document row for batch creation."""
        self.db.add(doc)

    async def prepare_batch_create(self, docs: list[Document]) -> None:
        """Flush ids and assign root_ids without committing yet."""
        if not docs:
            return
        await self.db.flush()
        for doc in docs:
            doc.root_id = doc.id

    async def commit_and_refresh_root_ids(self, docs: list[Document]) -> None:
        """Flush ids, set root_ids, and commit batch-created documents once."""
        await self.prepare_batch_create(docs)
        await self.db.commit()
        for doc in docs:
            await self.db.refresh(doc)

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        collection_id: int | None = None,
    ) -> tuple[list[tuple[Document, str | None]], int]:
        """Return paginated latest documents plus collection name."""
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
        """Fetch a document by id without user filtering."""
        result = await self.db.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, doc_id: int) -> Document | None:
        """Fetch a document by id scoped to the current user."""
        result = await self.db.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_versions_by_doc_id(self, doc_id: int) -> list[Document]:
        """Return the version chain for a document."""
        doc = await self.get_by_id(doc_id)
        if not doc:
            return []
        root_id = getattr(doc, "root_id", None) or doc.id
        stmt = (
            select(Document)
            .where(Document.root_id == root_id, Document.user_id == self.user_id)
            .order_by(Document.version.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_content(self, doc_id: int, content: str) -> Document | None:
        """Replace the content of an existing latest document."""
        doc = await self.get_by_id_for_user(doc_id)
        if not doc:
            return None
        doc.content = content
        doc.size = len(content.encode("utf-8"))
        doc.version = (doc.version or 1) + 1
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def create_version(
        self,
        doc_id: int,
        content: str,
        *,
        commit: bool = True,
    ) -> Document | None:
        """Create a new latest version row for a document."""
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
        new_doc = Document(
            user_id=self.user_id,
            title=orig.title,
            content=content,
            document_type=orig.document_type,
            size=len(content.encode("utf-8")),
            version=(max_version or 1) + 1,
            parent_id=orig.id,
            root_id=root_id,
            is_latest=True,
            collection_id=getattr(orig, "collection_id", None),
        )
        orig.is_latest = False
        self.db.add(new_doc)
        if commit:
            await self.db.commit()
            await self.db.refresh(new_doc)
        else:
            await self.db.flush()
        return new_doc

    async def get_by_ids(self, ids: list[int]) -> list[Document]:
        """Fetch multiple documents scoped to the current user."""
        if not ids:
            return []
        result = await self.db.execute(
            select(Document).where(
                Document.id.in_(ids),
                Document.user_id == self.user_id,
            )
        )
        return list(result.scalars().all())

    async def get_chain_by_root_ids(self, root_ids: set[int]) -> list[Document]:
        """Fetch all versions for each root id."""
        if not root_ids:
            return []
        result = await self.db.execute(
            select(Document).where(
                Document.root_id.in_(root_ids),
                Document.user_id == self.user_id,
            )
        )
        return list(result.scalars().all())

    async def delete_chain(self, docs: list[Document]) -> int:
        """Delete a full version chain."""
        for doc in docs:
            await self.db.delete(doc)
        await self.db.commit()
        return len(docs)

    async def count_total(self) -> int:
        """Count all documents in the table."""
        result = await self.db.execute(select(func.count()).select_from(Document))
        return result.scalar() or 0
