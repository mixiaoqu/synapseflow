"""
pgvector 向量存储服务
支持插入文档分块与余弦相似度检索
"""
from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Embedding


async def add_document_chunks(
    db: AsyncSession,
    document_id: int,
    chunks: List[str],
    vectors: List[List[float]],
) -> int:
    """
    将文档分块及对应向量写入 embeddings 表
    返回插入的 chunk 数量
    """
    if not chunks or len(chunks) != len(vectors):
        return 0
    rows = [
        Embedding(
            document_id=document_id,
            chunk_text=chunk,
            chunk_index=i,
            embedding=vec,
            metadata_={"chunk_index": i},
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors))
    ]
    db.add_all(rows)
    await db.commit()
    return len(rows)


async def delete_document_embeddings(db: AsyncSession, document_id: int) -> int:
    """删除指定文档的所有嵌入（文档删除时调用，CASCADE 也会处理）"""
    await db.execute(delete(Embedding).where(Embedding.document_id == document_id))
    await db.commit()
    return 0  # rowcount 在 async 中不便获取，调用方主要关心删除成功


delete_by_document_id = delete_document_embeddings


async def search(
    db: AsyncSession,
    query_embedding: List[float],
    k: int = 5,
) -> List[dict]:
    """
    基于 query 向量进行余弦相似度检索
    返回 [{"chunk_text": str, "document_id": int, "chunk_index": int, "distance": float}, ...]
    """
    stmt = (
        select(Embedding)
        .order_by(Embedding.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    out = []
    for row in rows:
        out.append({
            "chunk_text": row.chunk_text,
            "document_id": row.document_id,
            "chunk_index": row.chunk_index,
            "distance": getattr(row, "_distance", 0.0),
        })
    return out
