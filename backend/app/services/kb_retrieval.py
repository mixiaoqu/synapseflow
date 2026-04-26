"""Shared retrieval pipeline for KB chat, curation, and tools."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.core.config.registry import config_registry
from app.db.models import Document, KnowledgeBase
from app.db.session import AsyncSessionLocal
from app.repositories.access_scope import accessible_document_condition
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.document_index_state import INDEX_STATUS_INDEXED
from app.services.document_lifecycle import RETRIEVAL_VERSION_LIVE
from app.services.embedding import embed_query
from app.services.reranker import rerank
from app.services.vector_store import reciprocal_rank_fusion_many, search, search_hybrid_rrf


def _format_kb_chunk(doc: dict[str, Any], content: str) -> str:
    meta = doc.get("metadata", {}) or {}
    title = meta.get("document_title", "Unknown document")
    section_path = meta.get("section_path")
    header = f"[Document: {title}]"
    if section_path:
        header += f"\n[Section: {section_path}]"
    return f"{header}\n{content}"


def _apply_kb_context_budget(
    retrieved_docs: list[dict[str, Any]],
    max_chars: int,
) -> tuple[list[dict[str, Any]], str]:
    """Trim retrieved docs to fit the prompt context budget."""

    if not retrieved_docs:
        return [], ""
    if max_chars <= 0:
        parts = [_format_kb_chunk(doc, doc.get("content") or "") for doc in retrieved_docs]
        return retrieved_docs, "\n\n".join(parts)

    kept: list[dict[str, Any]] = []
    parts: list[str] = []
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
    team_id: int | None,
    knowledge_base_id: int,
    category_id: int | None,
    user_id: int | None,
    document_statuses: list[str] | None,
    retrieval_version_mode: str | None,
) -> bool:
    async with AsyncSessionLocal() as db:
        stmt = select(Document.id).where(
            Document.knowledge_base_id == knowledge_base_id,
            (
                Document.is_live.is_(True)
                if retrieval_version_mode == RETRIEVAL_VERSION_LIVE
                else Document.is_current.is_(True)
            ),
            Document.index_status == INDEX_STATUS_INDEXED,
        )
        if team_id is not None:
            stmt = stmt.join(KnowledgeBase, KnowledgeBase.id == Document.knowledge_base_id).where(
                KnowledgeBase.team_id == team_id
            )
        if category_id is not None:
            stmt = stmt.where(Document.category_id == category_id)
        if user_id is not None:
            stmt = stmt.where(accessible_document_condition(user_id))
        if document_statuses:
            stmt = stmt.where(Document.status.in_(document_statuses))
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


def _build_retrieval_funnel(
    *,
    mode: str,
    query_stats: list[dict[str, Any]],
    recalled_count: int,
    merged_count: int,
    reranked_count: int,
    context_count: int,
) -> dict[str, Any]:
    multi_query = len(query_stats) > 1
    stages: list[dict[str, Any]] = [
        {
            "key": "recalled_candidates",
            "label": "Initial Recall",
            "chunk_count": recalled_count,
            "note": (
                "Total recalled chunks across rewritten queries before merge."
                if multi_query
                else "Chunks recalled for the current query before filtering."
            ),
        }
    ]
    if multi_query:
        stages.append(
            {
                "key": "merged_candidates",
                "label": "Merged Candidates",
                "chunk_count": merged_count,
                "note": "Candidate chunks after multi-query RRF merge and dedupe.",
            }
        )
    stages.extend(
        [
            {
                "key": "reranked_candidates",
                "label": "Post Filter",
                "chunk_count": reranked_count,
                "note": "Chunks remaining after rerank and threshold filtering.",
            },
            {
                "key": "context_chunks",
                "label": "Context Chunks",
                "chunk_count": context_count,
                "note": "Chunks that finally enter the answer context.",
            },
        ]
    )
    return {
        "mode": mode,
        "query_count": len(query_stats),
        "rewritten_queries": query_stats,
        "stages": stages,
    }


async def _retrieve_candidate_rows(
    *,
    query: str,
    team_id: int | None,
    knowledge_base_id: int | None,
    category_id: int | None,
    user_id: int | None,
    retrieval_mode: str,
    recall_k: int,
    lexical_k: int = 0,
    document_statuses: list[str] | None = None,
    retrieval_version_mode: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    rag = config_registry.get_rag_config().retrieval
    query_embedding = await asyncio.to_thread(embed_query, query)

    async with AsyncSessionLocal() as db:
        if retrieval_mode == "hybrid":
            pool_limit = min(rag.hybrid_pool_limit, recall_k + max(lexical_k, 1))
            results = await search_hybrid_rrf(
                db,
                query_text=query,
                query_embedding=query_embedding,
                k_dense=recall_k,
                k_lexical=max(1, lexical_k),
                user_id=user_id,
                team_id=team_id,
                knowledge_base_id=knowledge_base_id,
                category_id=category_id,
                document_statuses=document_statuses,
                retrieval_version_mode=retrieval_version_mode,
                rrf_k=rag.rrf_k,
                pool_limit=max(pool_limit, 1),
            )
        else:
            results = await search(
                db,
                query_embedding,
                k=recall_k,
                user_id=user_id,
                team_id=team_id,
                knowledge_base_id=knowledge_base_id,
                category_id=category_id,
                document_statuses=document_statuses,
                retrieval_version_mode=retrieval_version_mode,
            )

    has_documents = True
    if knowledge_base_id is not None and not results:
        has_documents = await _knowledge_base_has_documents(
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            user_id=user_id,
            document_statuses=document_statuses,
            retrieval_version_mode=retrieval_version_mode,
        )

    return results, has_documents


def _meaningful_dense_distance(row: dict[str, Any]) -> float | None:
    raw_distance = row.get("distance")
    if raw_distance is None:
        return None
    try:
        return float(raw_distance)
    except (TypeError, ValueError):
        return None


def _passes_distance_threshold(row: dict[str, Any], threshold: float) -> bool:
    distance = _meaningful_dense_distance(row)
    return distance is None or distance <= threshold


def _passes_rerank_threshold(
    row: dict[str, Any],
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
    results: list[dict[str, Any]],
    *,
    iteration: int,
    rerank_enabled: bool,
) -> list[dict[str, Any]]:
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
            "[KB Retrieval] threshold filtering removed {} of {} candidates | distance_threshold={} rerank_threshold={}",
            removed,
            len(results),
            distance_threshold,
            rerank_threshold if rerank_enabled else "-",
        )
    return filtered


async def _finalize_ranked_rows(
    *,
    query: str,
    results: list[dict[str, Any]],
    rerank_enabled: bool,
    final_top_k: int,
    iteration: int,
) -> list[dict[str, Any]]:
    if rerank_enabled and results:
        logger.debug(
            "[KB Retrieval] preparing rerank | candidates={} keep={}",
            len(results),
            final_top_k,
        )
        results = await rerank(query, results, top_k=final_top_k)
    else:
        results = results[:final_top_k]
    return _apply_retrieval_thresholds(
        results,
        iteration=iteration,
        rerank_enabled=rerank_enabled,
    )


async def _expand_results_with_parent_context(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    child_chunk_ids = [int(row["document_chunk_id"]) for row in results]

    async with AsyncSessionLocal() as db:
        expansions = await DocumentChunkRepository(db).expand_parent_windows(
            child_chunk_ids=child_chunk_ids,
        )

    expanded_by_key: dict[int | str, dict[str, Any]] = {}
    ordered_keys: list[int | str] = []
    for row in results:
        document_chunk_id = int(row["document_chunk_id"])
        expansion = expansions.get(document_chunk_id)
        if expansion is None:
            logger.warning(
                "Skipping child chunk {} during retrieval because no persisted parent window was found",
                document_chunk_id,
            )
            continue
        updated = dict(row)
        metadata = dict(updated.get("metadata") or {})
        metadata.setdefault("child_chunk_id", document_chunk_id)
        metadata["parent_chunk_id"] = expansion.parent_chunk_id
        metadata["window_child_ids"] = list(expansion.window_child_ids)
        metadata["merged_child_chunk_ids"] = sorted(
            {document_chunk_id, *[int(item) for item in expansion.window_child_ids]}
        )
        metadata["evidence_text"] = row.get("chunk_text") or ""
        updated["metadata"] = metadata
        updated["chunk_text"] = expansion.content
        dedupe_key: int | str = (
            int(expansion.parent_chunk_id)
            if expansion.parent_chunk_id is not None
            else document_chunk_id
        )
        if dedupe_key not in expanded_by_key:
            expanded_by_key[dedupe_key] = updated
            ordered_keys.append(dedupe_key)
            continue

        existing = expanded_by_key[dedupe_key]
        existing_meta = dict(existing.get("metadata") or {})
        merged_child_ids = set(existing_meta.get("merged_child_chunk_ids") or [])
        merged_child_ids.add(document_chunk_id)
        merged_child_ids.update(int(item) for item in expansion.window_child_ids)
        existing_meta["merged_child_chunk_ids"] = sorted(merged_child_ids)
        existing_meta.setdefault("evidence_texts", [])
        if row.get("chunk_text"):
            existing_meta["evidence_texts"].append(row.get("chunk_text"))
        existing["metadata"] = existing_meta
        expanded_by_key[dedupe_key] = existing
    return [expanded_by_key[key] for key in ordered_keys]


async def _build_retrieval_output(
    *,
    results: list[dict[str, Any]],
    has_documents: bool,
    knowledge_base_id: int | None,
    category_id: int | None,
    iteration: int,
    log_prefix: str,
    retrieval_mode: str,
    recall_k: int,
    final_top_k: int,
    llm_ref_k: int | None,
    query_count: int,
    context_budget: int | None,
    retrieval_funnel: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rag = config_registry.get_rag_config().retrieval

    if llm_ref_k is not None:
        results = results[: max(1, llm_ref_k)]

    distances = [row.get("distance") for row in results if row.get("distance") is not None]
    rerank_scores = [
        row.get("rerank_score") for row in results if row.get("rerank_score") is not None
    ]
    dist_s = "{:.3f}~{:.3f}".format(min(distances), max(distances)) if distances else "-"
    rerank_s = (
        "{:.3f}~{:.3f}".format(min(rerank_scores), max(rerank_scores)) if rerank_scores else "-"
    )
    logger.info(
        "{} retrieval complete | iteration={} mode={} query_count={} results={} distance={} rerank={}",
        log_prefix,
        iteration + 1,
        retrieval_mode,
        query_count,
        len(results),
        dist_s,
        rerank_s,
    )
    logger.debug(
        "{} retrieval params | recall_k={} final_top_k={} llm_ref_k={}",
        log_prefix,
        recall_k,
        final_top_k,
        llm_ref_k if llm_ref_k is not None else "-",
    )

    if not results:
        if knowledge_base_id is not None and not has_documents:
            logger.warning(
                "{} knowledge base {} has no indexed documents",
                log_prefix,
                knowledge_base_id,
            )
            return {
                "retrieved_docs": [],
                "context": "(This knowledge base has no indexed documents yet.)",
                "kb_retrieval_status": "empty_knowledge_base",
                "retrieval_funnel": retrieval_funnel,
            }

        logger.warning(
            "{} no relevant content found | knowledge_base_id={} category_id={}",
            log_prefix,
            knowledge_base_id or "all",
            category_id or "all",
        )
        return {
            "retrieved_docs": [],
            "context": "(No relevant documents were found. Please confirm the KB has indexed content.)",
            "kb_retrieval_status": "no_hits",
            "retrieval_funnel": retrieval_funnel,
        }

    results = await _expand_results_with_parent_context(results)
    if not results:
        logger.warning(
            "{} retrieval candidates were discarded because persisted parent windows were missing",
            log_prefix,
        )
        return {
            "retrieved_docs": [],
            "context": "(No relevant documents were found. Please confirm the KB has indexed content.)",
            "kb_retrieval_status": "no_hits",
            "retrieval_funnel": retrieval_funnel,
        }

    retrieved_docs: list[dict[str, Any]] = []
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
            "{} context budget applied | budget={} kept={}/{}",
            log_prefix,
            budget,
            len(kept),
            len(retrieved_docs),
        )

    return {
        "retrieved_docs": kept,
        "context": context,
        "kb_retrieval_status": "ok",
        "retrieval_funnel": (
            {
                **retrieval_funnel,
                "stages": [
                    *list((retrieval_funnel or {}).get("stages") or [])[:-1],
                    {
                        "key": "context_chunks",
                        "label": "Context Chunks",
                        "chunk_count": len(kept),
                        "note": "Chunks that finally enter the answer context.",
                    },
                ],
            }
            if isinstance(retrieval_funnel, dict)
            else retrieval_funnel
        ),
    }


async def run_kb_retrieval(
    *,
    query: str,
    team_id: int | None,
    knowledge_base_id: int | None,
    category_id: int | None = None,
    iteration: int = 0,
    log_prefix: str = "[KB Retrieval]",
    user_id: int | None = None,
    result_limit: int | None = None,
    llm_reference_top_k: int | None = None,
    context_budget: int | None = None,
    document_statuses: list[str] | None = None,
    retrieval_version_mode: str | None = None,
    retrieval_mode: str | None = None,
    recall_k: int | None = None,
    lexical_k: int | None = None,
    rerank_enabled: bool | None = None,
) -> dict[str, Any]:
    """Retrieve KB chunks and return prompt-ready state."""

    rag = config_registry.get_rag_config().retrieval
    resolved_mode = str(retrieval_mode or ("hybrid" if rag.hybrid_enabled else "vector")).lower()
    resolved_recall_k = recall_k if recall_k is not None else (
        rag.k_iteration if iteration > 0 else rag.k_first
    )
    resolved_lexical_k = lexical_k if lexical_k is not None else rag.lexical_k
    final_top_k = max(1, result_limit) if result_limit is not None else rag.final_top_k
    llm_ref_k = (
        max(1, llm_reference_top_k)
        if llm_reference_top_k is not None
        else rag.llm_reference_top_k
    )
    resolved_rerank = settings.RERANK_ENABLED if rerank_enabled is None else bool(rerank_enabled)

    results, has_documents = await _retrieve_candidate_rows(
        query=query,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        user_id=user_id,
        retrieval_mode=resolved_mode,
        recall_k=resolved_recall_k,
        lexical_k=resolved_lexical_k,
        document_statuses=document_statuses,
        retrieval_version_mode=retrieval_version_mode,
    )
    raw_count = len(results)
    results = await _finalize_ranked_rows(
        query=query,
        results=results,
        rerank_enabled=resolved_rerank,
        final_top_k=final_top_k,
        iteration=iteration,
    )
    retrieval_funnel = _build_retrieval_funnel(
        mode=resolved_mode,
        query_stats=[{"query": query, "chunk_count": raw_count}],
        recalled_count=raw_count,
        merged_count=raw_count,
        reranked_count=len(results),
        context_count=len(results),
    )
    return await _build_retrieval_output(
        results=results,
        has_documents=has_documents,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        iteration=iteration,
        log_prefix=log_prefix,
        retrieval_mode=resolved_mode,
        recall_k=resolved_recall_k,
        final_top_k=final_top_k,
        llm_ref_k=llm_ref_k,
        query_count=1,
        context_budget=context_budget,
        retrieval_funnel=retrieval_funnel,
    )


async def run_multi_query_kb_retrieval(
    *,
    query: str,
    retrieval_queries: list[str],
    team_id: int | None,
    knowledge_base_id: int | None,
    category_id: int | None = None,
    iteration: int = 0,
    log_prefix: str = "[KB Retrieval]",
    user_id: int | None = None,
    result_limit: int | None = None,
    llm_reference_top_k: int | None = None,
    context_budget: int | None = None,
    document_statuses: list[str] | None = None,
    retrieval_version_mode: str | None = None,
    retrieval_mode: str | None = None,
    recall_k: int | None = None,
    lexical_k: int | None = None,
    rerank_enabled: bool | None = None,
) -> dict[str, Any]:
    """Retrieve KB chunks from multiple rewritten queries and fuse them with RRF."""

    queries = _dedupe_queries(retrieval_queries or [query])
    if len(queries) <= 1:
        output = await run_kb_retrieval(
            query=queries[0] if queries else query,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            iteration=iteration,
            log_prefix=log_prefix,
            user_id=user_id,
            result_limit=result_limit,
            llm_reference_top_k=llm_reference_top_k,
            context_budget=context_budget,
            document_statuses=document_statuses,
            retrieval_version_mode=retrieval_version_mode,
            retrieval_mode=retrieval_mode,
            recall_k=recall_k,
            lexical_k=lexical_k,
            rerank_enabled=rerank_enabled,
        )
        output["retrieval_queries"] = queries or [query]
        return output

    rag = config_registry.get_rag_config().retrieval
    resolved_mode = str(retrieval_mode or ("hybrid" if rag.hybrid_enabled else "vector")).lower()
    resolved_recall_k = recall_k if recall_k is not None else (
        rag.k_iteration if iteration > 0 else rag.k_first
    )
    resolved_lexical_k = lexical_k if lexical_k is not None else rag.lexical_k
    final_top_k = max(1, result_limit) if result_limit is not None else rag.final_top_k
    llm_ref_k = (
        max(1, llm_reference_top_k)
        if llm_reference_top_k is not None
        else rag.llm_reference_top_k
    )
    resolved_rerank = settings.RERANK_ENABLED if rerank_enabled is None else bool(rerank_enabled)
    per_query_recall_k = _scaled_candidate_k(len(queries), resolved_recall_k, final_top_k)
    per_query_lexical_k = (
        _scaled_candidate_k(len(queries), resolved_lexical_k, 1)
        if resolved_mode == "hybrid" and resolved_lexical_k > 0
        else 0
    )

    logger.debug("{} multi-query retrieval using queries={}", log_prefix, queries)
    batches = await asyncio.gather(
        *[
            _retrieve_candidate_rows(
                query=item,
                team_id=team_id,
                knowledge_base_id=knowledge_base_id,
                category_id=category_id,
                user_id=user_id,
                retrieval_mode=resolved_mode,
                recall_k=per_query_recall_k,
                lexical_k=per_query_lexical_k,
                document_statuses=document_statuses,
                retrieval_version_mode=retrieval_version_mode,
            )
            for item in queries
        ]
    )

    rankings = [rows for rows, _ in batches]
    query_stats = [
        {"query": item, "chunk_count": len(rows)}
        for item, (rows, _) in zip(queries, batches, strict=False)
    ]
    recalled_count = sum(item["chunk_count"] for item in query_stats)
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
        rerank_enabled=resolved_rerank,
        final_top_k=final_top_k,
        iteration=iteration,
    )
    retrieval_funnel = _build_retrieval_funnel(
        mode=resolved_mode,
        query_stats=query_stats,
        recalled_count=recalled_count,
        merged_count=len(fused_results),
        reranked_count=len(results),
        context_count=len(results),
    )
    output = await _build_retrieval_output(
        results=results,
        has_documents=has_documents,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        iteration=iteration,
        log_prefix=log_prefix,
        retrieval_mode=resolved_mode,
        recall_k=per_query_recall_k,
        final_top_k=final_top_k,
        llm_ref_k=llm_ref_k,
        query_count=len(queries),
        context_budget=context_budget,
        retrieval_funnel=retrieval_funnel,
    )
    output["retrieval_queries"] = queries
    return output
