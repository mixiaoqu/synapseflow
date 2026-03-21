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
    *,
    commit: bool = True,
) -> int:
    """
    将文档分块及对应向量写入 embeddings 表
    返回插入的 chunk 数量
    commit: 是否立即提交，False 时由调用方统一提交（用于与 indexed_at 等更新同事务）
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
    if commit:
        await db.commit()
    return len(rows)


async def delete_document_embeddings(
    db: AsyncSession, document_id: int, *, commit: bool = True
) -> int:
    """删除指定文档的所有嵌入（文档删除时调用，CASCADE 也会处理）"""
    await db.execute(delete(Embedding).where(Embedding.document_id == document_id))
    if commit:
        await db.commit()
    return 0  # rowcount 在 async 中不便获取，调用方主要关心删除成功


delete_by_document_id = delete_document_embeddings


async def search(
    db: AsyncSession,
    query_embedding: List[float],
    k: int = 5,
    document_ids: List[int] | None = None,
) -> List[dict]:
    """
    基于 query 向量进行余弦相似度检索
    document_ids: 可选，仅检索这些文档的 embeddings（用于按集合限定）
    返回 [{"chunk_text": str, "document_id": int, "chunk_index": int, "distance": float}, ...]
    distance 为余弦距离 [0, 2]，越小越相似
    """
    dist_col = Embedding.embedding.cosine_distance(query_embedding).label("distance")
    stmt = select(Embedding, dist_col)
    if document_ids:
        stmt = stmt.where(Embedding.document_id.in_(document_ids))
    stmt = stmt.order_by(dist_col).limit(k)
    result = await db.execute(stmt)
    rows = result.all()

    out = []
    for emb_row, dist_val in rows:
        d = float(dist_val) if dist_val is not None else 0.0
        out.append({
            "chunk_text": emb_row.chunk_text,
            "document_id": emb_row.document_id,
            "chunk_index": emb_row.chunk_index,
            "distance": d,
        })

    return out
