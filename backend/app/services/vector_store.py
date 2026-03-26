"""
pgvector 向量存储服务
支持插入文档分块与余弦相似度检索；可选全文词法通道（ts_rank_cd）与稠密向量 RRF 融合。
"""
from typing import List, Tuple

from loguru import logger
from sqlalchemy import delete, select, text
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


def reciprocal_rank_fusion(
    dense: List[dict],
    lexical: List[dict],
    *,
    rrf_k: int,
    limit: int,
) -> List[dict]:
    """
    Reciprocal Rank Fusion：合并向量序与词法序。
    每项须含 chunk_text、document_id、chunk_index；dense 可含 distance。
    """
    if not dense and not lexical:
        return []
    if not lexical:
        return dense[:limit]
    if not dense:
        return lexical[:limit]

    def _key(r: dict) -> Tuple[int, int]:
        return (int(r["document_id"]), int(r["chunk_index"]))

    by_key: dict[Tuple[int, int], dict] = {}
    scores: dict[Tuple[int, int], float] = {}

    for r in dense:
        k0 = _key(r)
        by_key.setdefault(k0, dict(r))

    for r in lexical:
        k0 = _key(r)
        if k0 not in by_key:
            by_key[k0] = {
                "chunk_text": r["chunk_text"],
                "document_id": r["document_id"],
                "chunk_index": r["chunk_index"],
                "distance": 2.0,
            }

    for rank, r in enumerate(dense):
        scores[_key(r)] = scores.get(_key(r), 0.0) + 1.0 / (rrf_k + rank + 1)

    for rank, r in enumerate(lexical):
        scores[_key(r)] = scores.get(_key(r), 0.0) + 1.0 / (rrf_k + rank + 1)

    ordered = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    out: List[dict] = []
    for k0 in ordered[:limit]:
        row = dict(by_key[k0])
        row["rrf_score"] = scores[k0]
        out.append(row)
    return out


async def search_lexical(
    db: AsyncSession,
    query_text: str,
    k: int,
    document_ids: List[int] | None = None,
) -> List[dict]:
    """
    PostgreSQL 全文检索（simple 配置 + ts_rank_cd）。
    说明：这是 PG 内置词法相关度，不是 Okapi BM25；中文在 simple 下多为单字词位，仍可作稀疏召回。
    """
    q = (query_text or "").strip()[:2000]
    if not q or k <= 0:
        return []

    try:
        if document_ids:
            sql = text(
                """
                SELECT chunk_text, document_id, chunk_index,
                       ts_rank_cd(chunk_tsv, websearch_to_tsquery('simple', :q)) AS lr
                FROM embeddings
                WHERE chunk_tsv @@ websearch_to_tsquery('simple', :q)
                  AND document_id = ANY(:doc_ids)
                ORDER BY lr DESC NULLS LAST
                LIMIT :lim
                """
            )
            res = await db.execute(
                sql, {"q": q, "lim": k, "doc_ids": list(document_ids)}
            )
        else:
            sql = text(
                """
                SELECT chunk_text, document_id, chunk_index,
                       ts_rank_cd(chunk_tsv, websearch_to_tsquery('simple', :q)) AS lr
                FROM embeddings
                WHERE chunk_tsv @@ websearch_to_tsquery('simple', :q)
                ORDER BY lr DESC NULLS LAST
                LIMIT :lim
                """
            )
            res = await db.execute(sql, {"q": q, "lim": k})
    except Exception as e:
        logger.warning("词法检索失败，已跳过: {}", e)
        return []

    out: List[dict] = []
    for chunk_text, document_id, chunk_index, lr in res.all():
        out.append({
            "chunk_text": chunk_text,
            "document_id": int(document_id),
            "chunk_index": int(chunk_index),
            "distance": 2.0,
            "lexical_rank": float(lr) if lr is not None else 0.0,
        })
    return out


async def search_hybrid_rrf(
    db: AsyncSession,
    *,
    query_text: str,
    query_embedding: List[float],
    k_dense: int,
    k_lexical: int,
    document_ids: List[int] | None,
    rrf_k: int,
    pool_limit: int,
) -> List[dict]:
    """稠密向量 + 词法全文 RRF 融合后再交给上层 Rerank。"""
    dense = await search(db, query_embedding, k=k_dense, document_ids=document_ids)
    lexical = await search_lexical(db, query_text, k=k_lexical, document_ids=document_ids)
    return reciprocal_rank_fusion(
        dense, lexical, rrf_k=rrf_k, limit=pool_limit
    )
