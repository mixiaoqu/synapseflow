"""
文档分块与向量索引服务
将文档内容分块、向量化后写入 embeddings 表
"""
import asyncio
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document
from app.db.session import AsyncSessionLocal
from app.services.embedding import embed_documents
from app.services.vector_store import add_document_chunks, delete_by_document_id

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _chunk_text(content: str) -> List[str]:
    """将文本分块"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
    )
    return splitter.split_text(content)


async def index_document(db: AsyncSession, doc_id: int, content: str) -> int:
    """
    对单篇文档建立向量索引
    先删除旧索引，再分块、嵌入、写入
    返回写入的 chunk 数量
    """
    if not content or not content.strip():
        return 0

    chunks = _chunk_text(content.strip())
    if not chunks:
        return 0

    # 同步 embedding 在线程池中执行，避免阻塞
    vectors = await asyncio.to_thread(embed_documents, chunks)

    await delete_by_document_id(db, doc_id)
    return await add_document_chunks(db, doc_id, chunks, vectors)


async def reindex_all() -> int:
    """对所有 documents 重新建立索引，返回处理的文档数"""
    total_docs = 0
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document))
        docs = result.scalars().all()
        for doc in docs:
            try:
                await index_document(session, doc.id, doc.content or "")
                total_docs += 1
            except Exception:
                pass  # 跳过失败文档
    return total_docs
