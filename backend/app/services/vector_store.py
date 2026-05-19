"""pgvector-backed vector store utilities."""

from __future__ import annotations

import asyncio
import re
from typing import List, Sequence, Tuple

from loguru import logger
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.registry import config_registry
from app.db.models import Document, DocumentCategory, DocumentChunk, Embedding, KnowledgeBase
from app.repositories.access_scope import accessible_document_condition
from app.services.document_index_state import INDEX_STATUS_INDEXED
from app.services.document_lifecycle import RETRIEVAL_VERSION_LIVE
from app.services.semantic_chunk import VectorIndexChunk

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_SQL_SPACE_CLASS = "[[:space:]]+"


def _is_live_retrieval(retrieval_version_mode: str | None) -> bool:
    return retrieval_version_mode == RETRIEVAL_VERSION_LIVE


def _document_version_sql_condition(retrieval_version_mode: str | None) -> str:
    return "d.is_live IS TRUE" if _is_live_retrieval(retrieval_version_mode) else "d.is_current IS TRUE"


async def add_document_chunks(
    db: AsyncSession,
    document_id: int,
    chunks: List[VectorIndexChunk],
    vectors: List[List[float]],
    *,
    document_chunk_ids: Sequence[int],
    commit: bool = True,
) -> int:
    """Insert chunk embeddings for a document."""
    if not chunks or len(chunks) != len(vectors):
        return 0
    if len(document_chunk_ids) != len(chunks):
        raise ValueError("document_chunk_ids must match chunk count")
    rows = [
        Embedding(
            document_id=document_id,
            document_chunk_id=int(document_chunk_ids[i]),
            chunk_text=chunk.display_text,
            search_text=chunk.search_text,
            chunk_index=int(chunk.metadata.get("chunk_index", i)),
            embedding=vec,
            metadata_={"chunk_index": int(chunk.metadata.get("chunk_index", i)), **chunk.metadata},
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


def _normalized_query_text(query_text: str) -> str:
    return re.sub(r"\s+", " ", (query_text or "").strip())[:2000]


def _compact_query_text(query_text: str) -> str:
    return re.sub(r"\s+", "", _normalized_query_text(query_text))


def _contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _build_ranked_row(
    *,
    chunk_text: str,
    search_text: str | None,
    document_id: int,
    chunk_index: int,
    document_chunk_id: int,
    raw_metadata: object,
    document_title: str | None,
    row_category_id: int | None,
    source_path: str | None,
    category_name: str | None,
    distance: float | None,
    lexical_rank: float | None = None,
    lexical_source: str | None = None,
) -> dict:
    metadata = dict(raw_metadata or {})
    metadata["document_chunk_id"] = int(document_chunk_id)
    metadata["category_id"] = int(row_category_id) if row_category_id is not None else None
    metadata["category_name"] = category_name
    metadata["source_path"] = source_path

    row = {
        "chunk_text": chunk_text,
        "search_text": search_text or chunk_text,
        "document_id": int(document_id),
        "chunk_index": int(chunk_index),
        "document_chunk_id": int(document_chunk_id),
        "metadata": metadata,
        "distance": float(distance) if distance is not None else None,
        "document_title": document_title or "Unknown document",
    }
    if lexical_rank is not None:
        row["lexical_rank"] = float(lexical_rank)
    if lexical_source is not None:
        row["lexical_source"] = lexical_source
    return row


async def search(
    db: AsyncSession,
    query_embedding: List[float],
    k: int = 5,
    *,
    user_id: int | None = None,
    team_id: int | None = None,
    knowledge_base_id: int | None = None,
    category_id: int | None = None,
    document_statuses: Sequence[str] | None = None,
    retrieval_version_mode: str | None = None,
) -> List[dict]:
    """
    Vector search across embeddings joined with the current document rows.

    Returns:
        [{"chunk_text", "document_id", "chunk_index", "distance", "document_title"}, ...]
    """
    dist_col = Embedding.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(
            Embedding.chunk_text,
            Embedding.search_text,
            Embedding.document_id,
            Embedding.chunk_index,
            Embedding.document_chunk_id,
            Embedding.metadata_,
            dist_col,
            Document.title.label("document_title"),
            Document.category_id.label("category_id"),
            Document.source_path.label("source_path"),
            DocumentCategory.name.label("category_name"),
        )
        .join(Document, Document.id == Embedding.document_id)
        .join(DocumentChunk, DocumentChunk.id == Embedding.document_chunk_id)
        .join(KnowledgeBase, KnowledgeBase.id == Document.knowledge_base_id)
        .outerjoin(DocumentCategory, Document.category_id == DocumentCategory.id)
        .where(
            Document.is_live.is_(True)
            if _is_live_retrieval(retrieval_version_mode)
            else Document.is_current.is_(True)
        )
        .where(Document.index_status == INDEX_STATUS_INDEXED)
        .where(DocumentChunk.chunk_kind == "child")
    )
    if user_id is not None:
        stmt = stmt.where(accessible_document_condition(user_id))
    if team_id is not None:
        stmt = stmt.where(KnowledgeBase.team_id == team_id)
    if knowledge_base_id is not None:
        stmt = stmt.where(Document.knowledge_base_id == knowledge_base_id)
    if category_id is not None:
        stmt = stmt.where(Document.category_id == category_id)
    if document_statuses:
        stmt = stmt.where(Document.status.in_(list(document_statuses)))
    stmt = stmt.order_by(dist_col).limit(k)

    result = await db.execute(stmt)
    out: List[dict] = []
    for (
        chunk_text,
        search_text,
        document_id,
        chunk_index,
        document_chunk_id,
        raw_metadata,
        dist_val,
        document_title,
        row_category_id,
        source_path,
        category_name,
    ) in result.all():
        out.append(
            _build_ranked_row(
                chunk_text=chunk_text,
                search_text=search_text,
                document_id=document_id,
                chunk_index=chunk_index,
                document_chunk_id=document_chunk_id,
                raw_metadata=raw_metadata,
                document_title=document_title,
                row_category_id=row_category_id,
                source_path=source_path,
                category_name=category_name,
                distance=float(dist_val) if dist_val is not None else 0.0,
            )
        )
    return out


def _ranked_row_key(row: dict) -> Tuple[str, int]:
    return ("chunk", int(row["document_chunk_id"]))


def _copy_ranked_row(row: dict) -> dict:
    return {
        "chunk_text": row["chunk_text"],
        "search_text": row.get("search_text", row["chunk_text"]),
        "document_id": int(row["document_id"]),
        "chunk_index": int(row["chunk_index"]),
        "document_chunk_id": int(row["document_chunk_id"]),
        "metadata": dict(row.get("metadata") or {}),
        "distance": (
            float(row["distance"])
            if row.get("distance") is not None
            else None
        ),
        "document_title": row.get("document_title", "Unknown document"),
        **(
            {"lexical_rank": float(row["lexical_rank"])}
            if row.get("lexical_rank") is not None
            else {}
        ),
        **({"lexical_source": row["lexical_source"]} if row.get("lexical_source") else {}),
    }


def _merge_ranked_row(existing: dict, incoming: dict) -> None:
    incoming_distance = (
        float(incoming["distance"])
        if incoming.get("distance") is not None
        else None
    )
    existing_distance = (
        float(existing["distance"])
        if existing.get("distance") is not None
        else None
    )
    if incoming_distance is not None and (
        existing_distance is None or incoming_distance < existing_distance
    ):
        existing["distance"] = incoming_distance
    if existing.get("document_title") == "Unknown document" and incoming.get("document_title"):
        existing["document_title"] = incoming["document_title"]
    if not existing.get("search_text") and incoming.get("search_text"):
        existing["search_text"] = incoming["search_text"]
    if incoming.get("lexical_rank") is not None:
        existing["lexical_rank"] = max(
            float(existing.get("lexical_rank", 0.0)),
            float(incoming["lexical_rank"]),
        )
    if not existing.get("lexical_source") and incoming.get("lexical_source"):
        existing["lexical_source"] = incoming["lexical_source"]
    existing_meta = existing.setdefault("metadata", {})
    for key, value in dict(incoming.get("metadata") or {}).items():
        existing_meta.setdefault(key, value)


def reciprocal_rank_fusion_many(
    rankings: Sequence[Sequence[dict]],
    *,
    rrf_k: int,
    limit: int,
    weights: Sequence[float] | None = None,
) -> List[dict]:
    """Merge multiple ranked lists with Reciprocal Rank Fusion."""

    non_empty = [rows for rows in rankings if rows]
    if not non_empty:
        return []
    if len(non_empty) == 1 and (not weights or len(weights) <= 1):
        return [dict(row) for row in list(non_empty[0])[:limit]]

    by_key: dict[Tuple[int | str, int], dict] = {}
    scores: dict[Tuple[int | str, int], float] = {}

    for list_index, rows in enumerate(rankings):
        if not rows:
            continue
        weight = float(weights[list_index]) if weights and list_index < len(weights) else 1.0
        for row in rows:
            key = _ranked_row_key(row)
            if key not in by_key:
                by_key[key] = _copy_ranked_row(row)
            else:
                _merge_ranked_row(by_key[key], row)
        for rank, row in enumerate(rows):
            key = _ranked_row_key(row)
            scores[key] = scores.get(key, 0.0) + weight / (rrf_k + rank + 1)

    ordered = sorted(scores.keys(), key=lambda item: scores[item], reverse=True)
    out: List[dict] = []
    for key in ordered[:limit]:
        row = dict(by_key[key])
        row["rrf_score"] = scores[key]
        out.append(row)
    return out


def reciprocal_rank_fusion(
    dense: List[dict],
    lexical: List[dict],
    *,
    rrf_k: int,
    limit: int,
) -> List[dict]:
    """Merge dense and lexical rankings with Reciprocal Rank Fusion."""

    return reciprocal_rank_fusion_many(
        [dense, lexical],
        rrf_k=rrf_k,
        limit=limit,
    )


async def _search_lexical_fts(
    db: AsyncSession,
    query_text: str,
    k: int,
    *,
    user_id: int | None = None,
    team_id: int | None = None,
    knowledge_base_id: int | None = None,
    category_id: int | None = None,
    document_statuses: Sequence[str] | None = None,
    retrieval_version_mode: str | None = None,
) -> List[dict]:
    """PostgreSQL full-text retrieval joined with document metadata."""

    query = _normalized_query_text(query_text)
    if not query or k <= 0:
        return []

    sql_lines = [
        "SELECT e.chunk_text, e.search_text, e.document_id, e.chunk_index, e.document_chunk_id, e.metadata, d.title AS document_title,",
        "       d.category_id, d.source_path, d.status, dc.name AS category_name,",
        "       ts_rank_cd(e.chunk_tsv, websearch_to_tsquery('simple', :q)) AS lr",
        "FROM embeddings e",
        "JOIN documents d ON d.id = e.document_id",
        "JOIN document_chunks c ON c.id = e.document_chunk_id AND c.chunk_kind = 'child'",
        "LEFT JOIN document_categories dc ON dc.id = d.category_id",
        "WHERE e.chunk_tsv @@ websearch_to_tsquery('simple', :q)",
        f"  AND {_document_version_sql_condition(retrieval_version_mode)}",
        "  AND d.index_status = 'indexed'",
    ]
    params: dict[str, object] = {"q": query, "lim": k}

    if user_id is not None:
        sql_lines.extend(
            [
                "  AND (",
                "    d.user_id = :user_id",
                "    OR EXISTS (",
                "      SELECT 1 FROM knowledge_bases kb",
                "      WHERE kb.id = d.knowledge_base_id",
                "        AND (",
                "          kb.user_id = :user_id",
                "          OR EXISTS (",
                "            SELECT 1 FROM team_members tm",
                "            WHERE tm.team_id = kb.team_id AND tm.user_id = :user_id",
                "          )",
                "          OR EXISTS (",
                "            SELECT 1 FROM knowledge_base_members kbm",
                "            WHERE kbm.knowledge_base_id = kb.id AND kbm.user_id = :user_id",
                "          )",
                "        )",
                "    )",
                "  )",
            ]
        )
        params["user_id"] = user_id
    if knowledge_base_id is not None:
        sql_lines.append("  AND d.knowledge_base_id = :knowledge_base_id")
        params["knowledge_base_id"] = knowledge_base_id
    if team_id is not None:
        sql_lines.append(
            "  AND EXISTS (SELECT 1 FROM knowledge_bases kb WHERE kb.id = d.knowledge_base_id AND kb.team_id = :team_id)"
        )
        params["team_id"] = team_id
    if category_id is not None:
        sql_lines.append("  AND d.category_id = :category_id")
        params["category_id"] = category_id
    sql_lines.extend(
        [
            "ORDER BY lr DESC NULLS LAST",
            "LIMIT :lim",
        ]
    )

    try:
        result = await db.execute(text("\n".join(sql_lines)), params)
    except Exception as exc:
        logger.warning("FTS lexical retrieval failed, skipping: {}", exc)
        return []

    out: List[dict] = []
    for (
        chunk_text,
        search_text,
        document_id,
        chunk_index,
        document_chunk_id,
        raw_metadata,
        document_title,
        row_category_id,
        source_path,
        document_status,
        category_name,
        lexical_rank,
    ) in result.all():
        if document_statuses and document_status not in set(document_statuses):
            continue
        out.append(
            _build_ranked_row(
                chunk_text=chunk_text,
                search_text=search_text,
                document_id=document_id,
                chunk_index=chunk_index,
                document_chunk_id=document_chunk_id,
                raw_metadata=raw_metadata,
                document_title=document_title,
                row_category_id=row_category_id,
                source_path=source_path,
                category_name=category_name,
                distance=None,
                lexical_rank=float(lexical_rank) if lexical_rank is not None else 0.0,
                lexical_source="fts",
            )
        )
    return out


async def _search_lexical_trgm(
    db: AsyncSession,
    query_text: str,
    k: int,
    *,
    user_id: int | None = None,
    team_id: int | None = None,
    knowledge_base_id: int | None = None,
    category_id: int | None = None,
    document_statuses: Sequence[str] | None = None,
    retrieval_version_mode: str | None = None,
) -> List[dict]:
    """Chinese-friendly phrase and trigram retrieval on ``search_text``."""

    query = _normalized_query_text(query_text)
    compact_query = _compact_query_text(query_text).lower()
    if not query or not compact_query or k <= 0:
        return []

    query_lower = query.lower()
    similarity_threshold = 0.08 if _contains_cjk(query) else 0.18
    word_threshold = 0.12 if _contains_cjk(query) else 0.2
    compact_expr = (
        f"regexp_replace(lower(e.search_text), '{_SQL_SPACE_CLASS}', '', 'g')"
    )
    sql_lines = [
        "SELECT e.chunk_text, e.search_text, e.document_id, e.chunk_index, e.document_chunk_id, e.metadata, d.title AS document_title,",
        "       d.category_id, d.source_path, d.status, dc.name AS category_name,",
        "       (",
        "         CASE WHEN lower(e.search_text) LIKE :phrase_like THEN 1.5 ELSE 0.0 END +",
        f"         CASE WHEN {compact_expr} LIKE :compact_like THEN 1.2 ELSE 0.0 END +",
        "         GREATEST(",
        "           similarity(lower(e.search_text), :q_lower),",
        "           word_similarity(lower(e.search_text), :q_lower),",
        f"           similarity({compact_expr}, :q_compact)",
        "         )",
        "       ) AS lr",
        "FROM embeddings e",
        "JOIN documents d ON d.id = e.document_id",
        "JOIN document_chunks c ON c.id = e.document_chunk_id AND c.chunk_kind = 'child'",
        "LEFT JOIN document_categories dc ON dc.id = d.category_id",
        f"WHERE {_document_version_sql_condition(retrieval_version_mode)}",
        "  AND d.index_status = 'indexed'",
        "  AND (",
        "    lower(e.search_text) LIKE :phrase_like",
        f"    OR {compact_expr} LIKE :compact_like",
        "    OR lower(e.search_text) % :q_lower",
        f"    OR similarity({compact_expr}, :q_compact) >= :sim_threshold",
        "    OR word_similarity(lower(e.search_text), :q_lower) >= :word_threshold",
        "  )",
    ]
    params: dict[str, object] = {
        "q_lower": query_lower,
        "q_compact": compact_query,
        "phrase_like": f"%{query_lower}%",
        "compact_like": f"%{compact_query}%",
        "sim_threshold": similarity_threshold,
        "word_threshold": word_threshold,
        "lim": k,
    }

    if user_id is not None:
        sql_lines.extend(
            [
                "  AND (",
                "    d.user_id = :user_id",
                "    OR EXISTS (",
                "      SELECT 1 FROM knowledge_bases kb",
                "      WHERE kb.id = d.knowledge_base_id",
                "        AND (",
                "          kb.user_id = :user_id",
                "          OR EXISTS (",
                "            SELECT 1 FROM team_members tm",
                "            WHERE tm.team_id = kb.team_id AND tm.user_id = :user_id",
                "          )",
                "          OR EXISTS (",
                "            SELECT 1 FROM knowledge_base_members kbm",
                "            WHERE kbm.knowledge_base_id = kb.id AND kbm.user_id = :user_id",
                "          )",
                "        )",
                "    )",
                "  )",
            ]
        )
        params["user_id"] = user_id
    if knowledge_base_id is not None:
        sql_lines.append("  AND d.knowledge_base_id = :knowledge_base_id")
        params["knowledge_base_id"] = knowledge_base_id
    if team_id is not None:
        sql_lines.append(
            "  AND EXISTS (SELECT 1 FROM knowledge_bases kb WHERE kb.id = d.knowledge_base_id AND kb.team_id = :team_id)"
        )
        params["team_id"] = team_id
    if category_id is not None:
        sql_lines.append("  AND d.category_id = :category_id")
        params["category_id"] = category_id
    sql_lines.extend(
        [
            "ORDER BY lr DESC NULLS LAST",
            "LIMIT :lim",
        ]
    )

    try:
        result = await db.execute(text("\n".join(sql_lines)), params)
    except Exception as exc:
        logger.warning("Trigram lexical retrieval failed, skipping: {}", exc)
        return []

    out: List[dict] = []
    for (
        chunk_text,
        search_text,
        document_id,
        chunk_index,
        document_chunk_id,
        raw_metadata,
        document_title,
        row_category_id,
        source_path,
        document_status,
        category_name,
        lexical_rank,
    ) in result.all():
        if document_statuses and document_status not in set(document_statuses):
            continue
        out.append(
            _build_ranked_row(
                chunk_text=chunk_text,
                search_text=search_text,
                document_id=document_id,
                chunk_index=chunk_index,
                document_chunk_id=document_chunk_id,
                raw_metadata=raw_metadata,
                document_title=document_title,
                row_category_id=row_category_id,
                source_path=source_path,
                category_name=category_name,
                distance=None,
                lexical_rank=float(lexical_rank) if lexical_rank is not None else 0.0,
                lexical_source="trgm",
            )
        )
    return out


async def search_lexical(
    db: AsyncSession,
    query_text: str,
    k: int,
    *,
    user_id: int | None = None,
    team_id: int | None = None,
    knowledge_base_id: int | None = None,
    category_id: int | None = None,
    document_statuses: Sequence[str] | None = None,
    retrieval_version_mode: str | None = None,
) -> List[dict]:
    """Chinese-aware lexical retrieval fused from FTS and trigram/phrase channels."""

    query = _normalized_query_text(query_text)
    if not query or k <= 0:
        return []

    rag = config_registry.get_rag_config().retrieval
    # One AsyncSession cannot safely provision or use the same connection for
    # concurrent statements, so run the lexical channels in sequence here.
    fts_rows = await _search_lexical_fts(
        db,
        query,
        k=k,
        user_id=user_id,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        document_statuses=document_statuses,
        retrieval_version_mode=retrieval_version_mode,
    )
    trgm_rows = await _search_lexical_trgm(
        db,
        query,
        k=k,
        user_id=user_id,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        document_statuses=document_statuses,
        retrieval_version_mode=retrieval_version_mode,
    )
    weights = [1.0, 1.2 if _contains_cjk(query) else 0.8]
    return reciprocal_rank_fusion_many(
        [fts_rows, trgm_rows],
        rrf_k=rag.rrf_k,
        limit=k,
        weights=weights,
    )


async def search_hybrid_rrf(
    db: AsyncSession,
    *,
    query_text: str,
    query_embedding: List[float],
    k_dense: int,
    k_lexical: int,
    user_id: int | None = None,
    team_id: int | None = None,
    knowledge_base_id: int | None = None,
    category_id: int | None = None,
    document_statuses: Sequence[str] | None = None,
    retrieval_version_mode: str | None = None,
    rrf_k: int = 60,
    pool_limit: int = 20,
) -> List[dict]:
    """Dense vector retrieval plus lexical retrieval fused with RRF."""

    dense = await search(
        db,
        query_embedding,
        k=k_dense,
        user_id=user_id,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        document_statuses=document_statuses,
        retrieval_version_mode=retrieval_version_mode,
    )
    lexical = await search_lexical(
        db,
        query_text,
        k=k_lexical,
        user_id=user_id,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        document_statuses=document_statuses,
        retrieval_version_mode=retrieval_version_mode,
    )
    return reciprocal_rank_fusion(dense, lexical, rrf_k=rrf_k, limit=pool_limit)
