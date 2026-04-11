"""Shared retrieval pipeline for KB chat, curation, and tools."""

import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.core.config.registry import config_registry
from app.db.models import Document
from app.db.session import AsyncSessionLocal
from app.services.embedding import embed_query
from app.services.reranker import rerank
from app.services.vector_store import reciprocal_rank_fusion_many, search, search_hybrid_rrf


def _format_kb_chunk(doc: Dict[str, Any], content: str) -> str:
    meta = doc.get("metadata", {}) or {}
    title = meta.get("document_title", "Unknown document")
    section_path = meta.get("section_path")
    header = f"[Document: {title}]"
    if section_path:
        header += f"\n[Section: {section_path}]"
    return f"{header}\n{content}"


def _apply_kb_context_budget(
    retrieved_docs: List[Dict[str, Any]],
    max_chars: int,
) -> tuple[List[Dict[str, Any]], str]:
    """Trim retrieved docs to fit the prompt context budget."""
    if not retrieved_docs:
        return [], ""
    if max_chars <= 0:
        parts = [_format_kb_chunk(doc, doc.get("content") or "") for doc in retrieved_docs]
        return retrieved_docs, "\n\n".join(parts)

    kept: List[Dict[str, Any]] = []
    parts: List[str] = []
    used = 0
    for doc in retrieved_docs:
        content = doc.get("content") or ""
        block = _format_kb_chunk(doc, content)
        gap = 2 if parts else 0
        if used + gap + len(block) <= max_chars:
            parts.append(block)
            kept.append(doc)
            used += gap + len(block)
            continue

        room = max_chars - used - gap
        title = doc.get("metadata", {}).get("document_title", "Unknown document")
        head = f"[Document: {title}]\n"
        if room <= len(head) + 16:
            break
        cutoff = room - len(head)
        snippet = content[:cutoff]
        if len(content) > cutoff:
            snippet += "..."
        truncated = dict(doc)
        truncated["content"] = snippet
        parts.append(_format_kb_chunk(truncated, snippet))
        kept.append(truncated)
        break

    return kept, "\n\n".join(parts)


async def _knowledge_base_has_documents(
    *,
    knowledge_base_id: int,
    category_id: int | None,
    user_id: int | None,
) -> bool:
    async with AsyncSessionLocal() as db:
        stmt = select(Document.id).where(
            Document.knowledge_base_id == knowledge_base_id,
            Document.is_current.is_(True),
        )
        if category_id is not None:
            stmt = stmt.where(Document.category_id == category_id)
        if user_id is not None:
            stmt = stmt.where(Document.user_id == user_id)
        result = await db.execute(stmt.limit(1))
        return result.scalar_one_or_none() is not None


def _dedupe_queries(queries: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = " ".join((query or "").split()).strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        out.append(normalized)
        seen.add(key)
    return out


def _scaled_candidate_k(total_queries: int, base_k: int, floor: int) -> int:
    if total_queries <= 1:
        return max(1, base_k)
    return max(floor, (base_k + total_queries - 1) // total_queries)


async def _retrieve_candidate_rows(
    *,
    query: str,
    knowledge_base_id: Optional[int],
    category_id: Optional[int],
    user_id: int | None,
    recall_k: int,
    lexical_k: int | None = None,
) -> tuple[List[dict], bool]:
    rag = config_registry.get_rag_config().retrieval
    query_embedding = await asyncio.to_thread(embed_query, query)
    lexical_limit = max(1, lexical_k if lexical_k is not None else rag.lexical_k)

    async with AsyncSessionLocal() as db:
        if rag.hybrid_enabled:
            pool_limit = min(rag.hybrid_pool_limit, recall_k + lexical_limit)
            results = await search_hybrid_rrf(
                db,
                query_text=query,
                query_embedding=query_embedding,
                k_dense=recall_k,
                k_lexical=lexical_limit,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                category_id=category_id,
                rrf_k=rag.rrf_k,
                pool_limit=max(pool_limit, 1),
            )
        else:
            results = await search(
                db,
                query_embedding,
                k=recall_k,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                category_id=category_id,
            )

    has_documents = True
    if knowledge_base_id is not None and not results:
        has_documents = await _knowledge_base_has_documents(
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            user_id=user_id,
        )

    return results, has_documents


async def _finalize_ranked_rows(
    *,
    query: str,
    results: List[dict],
    final_top_k: int,
    iteration: int,
) -> List[dict]:
    if settings.RERANK_ENABLED and results:
        logger.debug(
            "KB retrieval rerank candidates={} final_top_k={}",
            len(results),
            final_top_k,
        )
        results = await rerank(query, results, top_k=final_top_k)
    else:
        results = results[:final_top_k]
    return _apply_retrieval_thresholds(
        results,
        iteration=iteration,
        rerank_enabled=settings.RERANK_ENABLED,
    )


def _meaningful_dense_distance(row: dict) -> float | None:
    raw_distance = row.get("distance")
    if raw_distance is None:
        return None
    try:
        distance = float(raw_distance)
    except (TypeError, ValueError):
        return None
    return distance


def _passes_distance_threshold(row: dict, threshold: float) -> bool:
    distance = _meaningful_dense_distance(row)
    return distance is None or distance <= threshold


def _passes_rerank_threshold(
    row: dict,
    *,
    rerank_enabled: bool,
    threshold: float | None,
) -> bool:
    if not rerank_enabled or threshold is None:
        return True
    raw_score = row.get("rerank_score")
    if raw_score is None:
        return True
    try:
        return float(raw_score) >= threshold
    except (TypeError, ValueError):
        return False


def _apply_retrieval_thresholds(
    results: List[dict],
    *,
    iteration: int,
    rerank_enabled: bool,
) -> List[dict]:
    if not results:
        return []

    rag = config_registry.get_rag_config().retrieval
    distance_threshold = (
        rag.distance_threshold_iteration if iteration > 0 else rag.distance_threshold
    )
    rerank_threshold = rag.rerank_threshold

    filtered = [
        row
        for row in results
        if _passes_distance_threshold(row, distance_threshold)
        and _passes_rerank_threshold(
            row,
            rerank_enabled=rerank_enabled,
            threshold=rerank_threshold,
        )
    ]
    removed = len(results) - len(filtered)
    if removed:
        logger.info(
            "KB retrieval thresholds filtered {} of {} rows | distance<= {:.3f} rerank>= {}",
            removed,
            len(results),
            distance_threshold,
            (
                f"{rerank_threshold:.3f}"
                if rerank_enabled and rerank_threshold is not None
                else "-"
            ),
        )
    return filtered


def _build_retrieval_output(
    *,
    results: List[dict],
    has_documents: bool,
    knowledge_base_id: Optional[int],
    category_id: Optional[int],
    iteration: int,
    log_prefix: str,
    recall_k: int,
    final_top_k: int,
    llm_ref_k: int | None,
    query_count: int,
    context_budget: int | None,
) -> Dict[str, Any]:
    rag = config_registry.get_rag_config().retrieval

    if llm_ref_k is not None:
        results = results[: max(1, llm_ref_k)]

    mode = "hybrid" if rag.hybrid_enabled else "vector"
    distances = [row.get("distance") for row in results if row.get("distance") is not None]
    rerank_scores = [
        row.get("rerank_score") for row in results if row.get("rerank_score") is not None
    ]
    dist_s = "{:.3f}~{:.3f}".format(min(distances), max(distances)) if distances else "-"
    rerank_s = (
        "{:.3f}~{:.3f}".format(min(rerank_scores), max(rerank_scores))
        if rerank_scores
        else "-"
    )
    logger.info(
        "{} round={} mode={} query_count={} result_count={} distance={} rerank={}",
        log_prefix,
        iteration + 1,
        mode,
        query_count,
        len(results),
        dist_s,
        rerank_s,
    )
    logger.debug(
        "{} recall_k={} final_top_k={} llm_ref_k={}",
        log_prefix,
        recall_k,
        final_top_k,
        llm_ref_k if llm_ref_k is not None else "-",
    )

    if not results:
        if knowledge_base_id is not None and not has_documents:
            logger.warning(
                "{} knowledge_base_id={} has no indexed documents",
                log_prefix,
                knowledge_base_id,
            )
            return {
                "retrieved_docs": [],
                "context": "(This knowledge base has no indexed documents yet.)",
                "kb_retrieval_status": "empty_knowledge_base",
            }

        logger.warning(
            "{} no hits | knowledge_base={} category={}",
            log_prefix,
            knowledge_base_id or "all",
            category_id or "all",
        )
        return {
            "retrieved_docs": [],
            "context": "(No relevant documents were found. Please confirm the KB has indexed content.)",
            "kb_retrieval_status": "no_hits",
        }

    retrieved_docs = []
    for row in results:
        chunk_meta = dict(row.get("metadata") or {})
        meta = {
            **chunk_meta,
            "document_id": row["document_id"],
            "document_title": row.get("document_title", "Unknown document"),
            "chunk_index": row["chunk_index"],
            "score": row.get("distance"),
        }
        if row.get("rerank_score") is not None:
            meta["rerank_score"] = row["rerank_score"]
        retrieved_docs.append({"content": row["chunk_text"], "metadata": meta})

    budget = rag.kb_context_max_chars if context_budget is None else context_budget
    kept, context = _apply_kb_context_budget(retrieved_docs, budget)
    if budget > 0 and len(kept) < len(retrieved_docs):
        logger.info(
            "{} context trimmed to {} chars, kept {} of {} chunks",
            log_prefix,
            budget,
            len(kept),
            len(retrieved_docs),
        )

    return {
        "retrieved_docs": kept,
        "context": context,
        "kb_retrieval_status": "ok",
    }


async def run_kb_retrieval(
    *,
    query: str,
    knowledge_base_id: Optional[int],
    category_id: Optional[int] = None,
    iteration: int = 0,
    log_prefix: str = "[KB Retrieval]",
    user_id: int | None = None,
    result_limit: int | None = None,
    context_budget: int | None = None,
) -> Dict[str, Any]:
    """Retrieve KB chunks and return prompt-ready state."""

    rag = config_registry.get_rag_config().retrieval
    recall_k = rag.k_iteration if iteration > 0 else rag.k_first
    final_top_k = max(1, result_limit) if result_limit is not None else rag.final_top_k
    llm_ref_k = max(1, result_limit) if result_limit is not None else rag.llm_reference_top_k

    results, has_documents = await _retrieve_candidate_rows(
        query=query,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        user_id=user_id,
        recall_k=recall_k,
    )
    results = await _finalize_ranked_rows(
        query=query,
        results=results,
        final_top_k=final_top_k,
        iteration=iteration,
    )
    return _build_retrieval_output(
        results=results,
        has_documents=has_documents,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        iteration=iteration,
        log_prefix=log_prefix,
        recall_k=recall_k,
        final_top_k=final_top_k,
        llm_ref_k=llm_ref_k,
        query_count=1,
        context_budget=context_budget,
    )


async def run_multi_query_kb_retrieval(
    *,
    query: str,
    retrieval_queries: list[str],
    knowledge_base_id: Optional[int],
    category_id: Optional[int] = None,
    iteration: int = 0,
    log_prefix: str = "[KB Retrieval]",
    user_id: int | None = None,
    result_limit: int | None = None,
    context_budget: int | None = None,
) -> Dict[str, Any]:
    """Retrieve KB chunks from multiple rewritten queries and fuse them with RRF."""

    queries = _dedupe_queries(retrieval_queries or [query])
    if len(queries) <= 1:
        output = await run_kb_retrieval(
            query=queries[0] if queries else query,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            iteration=iteration,
            log_prefix=log_prefix,
            user_id=user_id,
            result_limit=result_limit,
            context_budget=context_budget,
        )
        output["retrieval_queries"] = queries or [query]
        return output

    rag = config_registry.get_rag_config().retrieval
    recall_k = rag.k_iteration if iteration > 0 else rag.k_first
    final_top_k = max(1, result_limit) if result_limit is not None else rag.final_top_k
    llm_ref_k = max(1, result_limit) if result_limit is not None else rag.llm_reference_top_k
    per_query_recall_k = _scaled_candidate_k(len(queries), recall_k, final_top_k)
    per_query_lexical_k = _scaled_candidate_k(len(queries), rag.lexical_k, final_top_k)

    logger.debug("{} multi-query retrieval queries={}", log_prefix, queries)
    batches = await asyncio.gather(
        *[
            _retrieve_candidate_rows(
                query=item,
                knowledge_base_id=knowledge_base_id,
                category_id=category_id,
                user_id=user_id,
                recall_k=per_query_recall_k,
                lexical_k=per_query_lexical_k,
            )
            for item in queries
        ]
    )

    rankings = [rows for rows, _ in batches]
    has_documents = all(has_docs for _, has_docs in batches)
    fused_limit = min(rag.hybrid_pool_limit, max(final_top_k, final_top_k * len(queries)))
    fused_results = reciprocal_rank_fusion_many(
        rankings,
        rrf_k=rag.rrf_k,
        limit=fused_limit,
        weights=[1.25] + [1.0] * (len(queries) - 1),
    )
    results = await _finalize_ranked_rows(
        query=query,
        results=fused_results,
        final_top_k=final_top_k,
        iteration=iteration,
    )
    output = _build_retrieval_output(
        results=results,
        has_documents=has_documents,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        iteration=iteration,
        log_prefix=log_prefix,
        recall_k=per_query_recall_k,
        final_top_k=final_top_k,
        llm_ref_k=llm_ref_k,
        query_count=len(queries),
        context_budget=context_budget,
    )
    output["retrieval_queries"] = queries
    return output
