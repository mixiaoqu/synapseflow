"""
文档分块与向量索引服务
将文档内容分块、向量化后写入 embeddings 表
"""
import asyncio
from datetime import datetime
from typing import List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from app.core.config.registry import config_registry
from app.core.constants import DEFAULT_USER_ID
from app.db.models import Document
from app.db.session import AsyncSessionLocal
from app.services.embedding import embed_documents
from app.services.semantic_chunk import split_for_vector_index
from app.services.vector_store import add_document_chunks, delete_by_document_id


def _chunk_text(content: str) -> List[str]:
    """按标题/段落语义分块；参数见 config/embedding.yaml chunk（size=单块上限，overlap=超长细分时重叠）。"""
    ck = config_registry.get_rag_config()["chunk"]
    return split_for_vector_index(
        content,
        max_chars=ck["size"],
        overlap=ck["overlap"],
    )


async def index_document(db: AsyncSession, doc_id: int, content: str) -> int:
    """
    对单篇文档建立向量索引
    先删除旧索引，再分块、嵌入、写入
    返回写入的 chunk 数量
    修改 chunk.size/overlap 或分块策略后需对已入库文档重新索引方可生效。
    """
    if not content or not content.strip():
        return 0

    chunks = _chunk_text(content.strip())
    if not chunks:
        return 0

    # 同步 embedding 在线程池中执行，避免阻塞
    vectors = await asyncio.to_thread(embed_documents, chunks)

    await delete_by_document_id(db, doc_id, commit=False)
    count = await add_document_chunks(db, doc_id, chunks, vectors, commit=False)
    if count > 0:
        await db.execute(update(Document).where(Document.id == doc_id).values(indexed_at=datetime.utcnow()))
    await db.commit()
    return count


async def reindex_all() -> int:
    """仅对 is_latest=True 的文档重新建立索引，返回成功索引的文档数"""
    total_docs = 0
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(
                Document.is_latest.is_(True)
            )
        )
        docs = result.scalars().all()
        for doc in docs:
            try:
                await index_document(session, doc.id, doc.content or "")
                total_docs += 1
            except Exception as e:
                logger.warning("索引失败 doc={} 《{}》: {}", doc.id, doc.title, e)
    return total_docs
