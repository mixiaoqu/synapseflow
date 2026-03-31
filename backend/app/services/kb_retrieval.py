"""Shared retrieval pipeline for KB chat, curation, and tools."""

import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.core.config.registry import config_registry
from app.core.constants import DEFAULT_USER_ID
from app.db.models import Document
from app.db.session import AsyncSessionLocal
from app.services.embedding import embed_query
from app.services.reranker import rerank
from app.services.vector_store import search, search_hybrid_rrf


def _format_kb_chunk(doc: Dict[str, Any], content: str) -> str:
    title = doc.get("metadata", {}).get("document_title", "未知文档")
    return "【文档：%s】\n%s" % (title, content)


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
        title = doc.get("metadata", {}).get("document_title", "未知文档")
        head = "【文档：%s】\n" % title
        if room <= len(head) + 16:
            break
        cutoff = room - len(head)
        snippet = content[:cutoff]
        if len(content) > cutoff:
            snippet += "…"
        truncated = dict(doc)
        truncated["content"] = snippet
        parts.append(_format_kb_chunk(truncated, snippet))
        kept.append(truncated)
        break

    return kept, "\n\n".join(parts)


async def _collection_has_documents(
    *,
    collection_id: int,
    user_id: int,
) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document.id)
            .where(
                Document.user_id == user_id,
                Document.collection_id == collection_id,
                Document.is_latest.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


async def _retrieve_ranked_rows(
    *,
    query: str,
    collection_id: Optional[int],
    user_id: int,
    recall_k: int,
    final_top_k: int,
) -> tuple[List[dict], bool]:
    rag = config_registry.get_rag_config().retrieval
    query_embedding = await asyncio.to_thread(embed_query, query)

    async with AsyncSessionLocal() as db:
        if rag.hybrid_enabled:
            pool_limit = min(rag.hybrid_pool_limit, recall_k + rag.lexical_k)
            results = await search_hybrid_rrf(
                db,
                query_text=query,
                query_embedding=query_embedding,
                k_dense=recall_k,
                k_lexical=rag.lexical_k,
                user_id=user_id,
                collection_id=collection_id,
                rrf_k=rag.rrf_k,
                pool_limit=max(pool_limit, 1),
            )
        else:
            results = await search(
                db,
                query_embedding,
                k=recall_k,
                user_id=user_id,
                collection_id=collection_id,
            )

    recall_n = len(results)
    if settings.RERANK_ENABLED and results:
        logger.debug(
            "知识库检索 精排候选 {} 条（目标截断 {}）",
            recall_n,
            final_top_k,
        )
        results = await rerank(query, results, top_k=final_top_k)
    else:
        results = results[:final_top_k]

    has_documents = True
    if collection_id is not None and recall_n == 0:
        has_documents = await _collection_has_documents(
            collection_id=collection_id,
            user_id=user_id,
        )

    return results, has_documents


async def run_kb_retrieval(
    *,
    query: str,
    collection_id: Optional[int],
    iteration: int = 0,
    log_prefix: str = "[知识库检索]",
    user_id: int = DEFAULT_USER_ID,
    result_limit: int | None = None,
    context_budget: int | None = None,
) -> Dict[str, Any]:
    """
    Retrieve KB chunks, apply rerank/context budget, and return prompt-ready state.

    Returns:
        {"retrieved_docs", "context", "kb_retrieval_status"}
    """
    rag = config_registry.get_rag_config().retrieval
    recall_k = rag.k_iteration if iteration > 0 else rag.k_first
    final_top_k = max(1, result_limit) if result_limit is not None else rag.final_top_k
    llm_ref_k = max(1, result_limit) if result_limit is not None else rag.llm_reference_top_k

    results, has_documents = await _retrieve_ranked_rows(
        query=query,
        collection_id=collection_id,
        user_id=user_id,
        recall_k=recall_k,
        final_top_k=final_top_k,
    )

    recall_n = len(results)
    if llm_ref_k is not None:
        results = results[: max(1, llm_ref_k)]

    mode = "向量+词法" if rag.hybrid_enabled else "向量"
    distances = [row.get("distance") for row in results if row.get("distance") is not None]
    rerank_scores = [
        row.get("rerank_score") for row in results if row.get("rerank_score") is not None
    ]
    dist_s = (
        "{:.3f}~{:.3f}".format(min(distances), max(distances))
        if distances
        else "-"
    )
    rerank_s = (
        "{:.3f}~{:.3f}".format(min(rerank_scores), max(rerank_scores))
        if rerank_scores
        else "-"
    )
    logger.info(
        "{} 第{}轮 {} | 入模 {} 条 | 距离 {} | 精排 {}",
        log_prefix,
        iteration + 1,
        mode,
        len(results),
        dist_s,
        rerank_s,
    )
    logger.debug(
        "{} 细节 recall_k={} final_top_k={} llm_ref_k={}",
        log_prefix,
        recall_k,
        final_top_k,
        llm_ref_k if llm_ref_k is not None else "-",
    )

    if not results:
        if collection_id is not None and not has_documents:
            logger.warning("{} 集合={} 下暂无已索引文档", log_prefix, collection_id)
            return {
                "retrieved_docs": [],
                "context": "（该集合暂无已索引文档，请先上传并建立索引）",
                "kb_retrieval_status": "empty_collection",
            }

        logger.warning("{} 无命中 | 集合={}", log_prefix, collection_id or "全库")
        return {
            "retrieved_docs": [],
            "context": "（未检索到相关文档，请确认文档库中有内容并已建立索引）",
            "kb_retrieval_status": "no_hits",
        }

    retrieved_docs = []
    for row in results:
        meta = {
            "document_id": row["document_id"],
            "document_title": row.get("document_title", "未知文档"),
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
            "{} 摘录限长 {} 字，送入模型 {} 条（原 {} 条）",
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
