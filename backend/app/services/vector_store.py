"""pgvector-backed vector store utilities."""

from typing import List, Tuple

from loguru import logger
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, Embedding


async def add_document_chunks(
    db: AsyncSession,
    document_id: int,
    chunks: List[str],
    vectors: List[List[float]],
    *,
    commit: bool = True,
) -> int:
    """Insert chunk embeddings for a document."""
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
    db: AsyncSession,
    document_id: int,
    *,
    commit: bool = True,
) -> int:
    """Delete all embeddings for a document."""
    await db.execute(delete(Embedding).where(Embedding.document_id == document_id))
    if commit:
        await db.commit()
    return 0


delete_by_document_id = delete_document_embeddings


async def search(
    db: AsyncSession,
    query_embedding: List[float],
    k: int = 5,
    *,
    user_id: int | None = None,
    knowledge_base_id: int | None = None,
) -> List[dict]:
    """
    Vector search across embeddings joined with the latest document rows.

    Returns:
        [{"chunk_text", "document_id", "chunk_index", "distance", "document_title"}, ...]
    """
    dist_col = Embedding.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(
            Embedding.chunk_text,
            Embedding.document_id,
            Embedding.chunk_index,
            dist_col,
            Document.title.label("document_title"),
        )
        .join(Document, Document.id == Embedding.document_id)
        .where(Document.is_latest.is_(True))
    )
    if user_id is not None:
        stmt = stmt.where(Document.user_id == user_id)
    if knowledge_base_id is not None:
        stmt = stmt.where(Document.knowledge_base_id == knowledge_base_id)
    stmt = stmt.order_by(dist_col).limit(k)

    result = await db.execute(stmt)
    out: List[dict] = []
    for chunk_text, document_id, chunk_index, dist_val, document_title in result.all():
        out.append(
            {
                "chunk_text": chunk_text,
                "document_id": int(document_id),
                "chunk_index": int(chunk_index),
                "distance": float(dist_val) if dist_val is not None else 0.0,
                "document_title": document_title or "Unknown document",
            }
        )
    return out


def reciprocal_rank_fusion(
    dense: List[dict],
    lexical: List[dict],
    *,
    rrf_k: int,
    limit: int,
) -> List[dict]:
    """Merge dense and lexical rankings with Reciprocal Rank Fusion."""
    if not dense and not lexical:
        return []
    if not lexical:
        return dense[:limit]
    if not dense:
        return lexical[:limit]

    def _key(row: dict) -> Tuple[int, int]:
        return (int(row["document_id"]), int(row["chunk_index"]))

    by_key: dict[Tuple[int, int], dict] = {}
    scores: dict[Tuple[int, int], float] = {}

    for row in dense:
        by_key.setdefault(_key(row), dict(row))

    for row in lexical:
        key = _key(row)
        if key not in by_key:
            by_key[key] = {
                "chunk_text": row["chunk_text"],
                "document_id": row["document_id"],
                "chunk_index": row["chunk_index"],
                "distance": 2.0,
                "document_title": row.get("document_title", "Unknown document"),
            }

    for rank, row in enumerate(dense):
        key = _key(row)
        scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)

    for rank, row in enumerate(lexical):
        key = _key(row)
        scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)

    ordered = sorted(scores.keys(), key=lambda item: scores[item], reverse=True)
    out: List[dict] = []
    for key in ordered[:limit]:
        row = dict(by_key[key])
        row["rrf_score"] = scores[key]
        out.append(row)
    return out


async def search_lexical(
    db: AsyncSession,
    query_text: str,
    k: int,
    *,
    user_id: int | None = None,
    knowledge_base_id: int | None = None,
) -> List[dict]:
    """PostgreSQL full-text retrieval joined with document metadata."""
    query = (query_text or "").strip()[:2000]
    if not query or k <= 0:
        return []

    sql_lines = [
        "SELECT e.chunk_text, e.document_id, e.chunk_index, d.title AS document_title,",
        "       ts_rank_cd(e.chunk_tsv, websearch_to_tsquery('simple', :q)) AS lr",
        "FROM embeddings e",
        "JOIN documents d ON d.id = e.document_id",
        "WHERE e.chunk_tsv @@ websearch_to_tsquery('simple', :q)",
        "  AND d.is_latest IS TRUE",
    ]
    params: dict[str, object] = {"q": query, "lim": k}

    if user_id is not None:
        sql_lines.append("  AND d.user_id = :user_id")
        params["user_id"] = user_id
    if knowledge_base_id is not None:
        sql_lines.append("  AND d.knowledge_base_id = :knowledge_base_id")
        params["knowledge_base_id"] = knowledge_base_id

    sql_lines.extend(
        [
            "ORDER BY lr DESC NULLS LAST",
            "LIMIT :lim",
        ]
    )

    try:
        result = await db.execute(text("\n".join(sql_lines)), params)
    except Exception as exc:
        logger.warning("Lexical retrieval failed, skipping: {}", exc)
        return []

    out: List[dict] = []
    for chunk_text, document_id, chunk_index, document_title, lexical_rank in result.all():
        out.append(
            {
                "chunk_text": chunk_text,
                "document_id": int(document_id),
                "chunk_index": int(chunk_index),
                "distance": 2.0,
                "lexical_rank": float(lexical_rank) if lexical_rank is not None else 0.0,
                "document_title": document_title or "Unknown document",
            }
        )
    return out


async def search_hybrid_rrf(
    db: AsyncSession,
    *,
    query_text: str,
    query_embedding: List[float],
    k_dense: int,
    k_lexical: int,
    user_id: int | None,
    knowledge_base_id: int | None,
    rrf_k: int,
    pool_limit: int,
) -> List[dict]:
    """Dense vector retrieval plus lexical retrieval fused with RRF."""
    dense = await search(
        db,
        query_embedding,
        k=k_dense,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
    )
    lexical = await search_lexical(
        db,
        query_text,
        k=k_lexical,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
    )
    return reciprocal_rank_fusion(dense, lexical, rrf_k=rrf_k, limit=pool_limit)
