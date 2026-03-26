"""
知识库向量检索（迭代 QA 与用户问答共用实现）。
"""
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
from app.services.vector_store import search, search_hybrid_rrf

DEFAULT_USER_ID = 1


async def run_kb_retrieval(
    *,
    query: str,
    collection_id: Optional[int],
    iteration: int = 0,
    log_prefix: str = "[知识库检索]",
) -> Dict[str, Any]:
    """
    从 pgvector 检索文档块，拼上下文。
    返回 {"retrieved_docs": [...], "context": str}
    """
    rag = config_registry.get_rag_config()["retrieval"]
    k = rag["k_iteration"] if iteration > 0 else rag["k_first"]
    final_top_k = rag["final_top_k"]
    llm_ref_k_raw = rag.get("llm_reference_top_k")
    llm_ref_k = int(llm_ref_k_raw) if llm_ref_k_raw is not None else None

    query_embedding = await asyncio.to_thread(embed_query, query)

    document_ids: Optional[List[int]] = None
    if collection_id is not None:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(Document.id).where(
                    Document.user_id == DEFAULT_USER_ID,
                    Document.collection_id == collection_id,
                    Document.is_latest.is_(True),
                )
            )
            document_ids = list(r.scalars().all()) or []
            if not document_ids:
                return {
                    "retrieved_docs": [],
                    "context": "（该集合暂无已索引文档，请先上传并建立索引）",
                }

    async with AsyncSessionLocal() as db:
        if rag.get("hybrid_enabled"):
            pool_limit = min(
                int(rag.get("hybrid_pool_limit", 64)),
                k + int(rag.get("lexical_k", 32)),
            )
            results = await search_hybrid_rrf(
                db,
                query_text=query,
                query_embedding=query_embedding,
                k_dense=k,
                k_lexical=int(rag.get("lexical_k", 32)),
                document_ids=document_ids,
                rrf_k=int(rag.get("rrf_k", 60)),
                pool_limit=max(pool_limit, 1),
            )
        else:
            results = await search(db, query_embedding, k=k, document_ids=document_ids)

    recall_n = len(results)
    coll_hint = collection_id if collection_id is not None else "全库"
    doc_hint = (
        len(document_ids)
        if document_ids is not None
        else "全库"
    )
    if recall_n == 0:
        logger.warning(
            "{} 无命中 | 集合={} | 候选文档={}（查索引、is_latest）",
            log_prefix,
            coll_hint,
            doc_hint,
        )
    rerank_applied = False
    if settings.RERANK_ENABLED and len(results) > 0:
        logger.debug(
            "{} 精排候选 {} 条（截断目标 {}）",
            log_prefix,
            len(results),
            final_top_k,
        )
        results = await rerank(query, results, top_k=final_top_k)
        rerank_applied = True
    else:
        logger.debug("{} 未开精排或无结果，截断 {} 条", log_prefix, final_top_k)
        results = results[:final_top_k]

    after_rank_len = len(results)
    if llm_ref_k is not None:
        n = max(1, llm_ref_k)
        results = results[:n]

    title_map: Dict[int, str] = {}
    if results:
        unique_ids = list({r["document_id"] for r in results})
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(Document.id, Document.title).where(Document.id.in_(unique_ids))
            )
            for row in r.all():
                title_map[row.id] = row.title or "未知文档"

    distances = [r.get("distance") for r in results if r.get("distance") is not None]
    rerank_scores = [r.get("rerank_score") for r in results if r.get("rerank_score") is not None]
    mode = "向量+词法" if rag.get("hybrid_enabled") else "向量"
    if distances:
        dmin, dmax = min(distances), max(distances)
        dist_s = "{:.3f}~{:.3f}".format(dmin, dmax)
    else:
        dist_s = "-"
    if rerank_scores:
        smin, smax = min(rerank_scores), max(rerank_scores)
        rr_s = "{:.3f}~{:.3f}".format(smin, smax)
    else:
        rr_s = "-"
    logger.info(
        "{} 第{}轮 {} | 召回 {} → 精排后 {} → 入模型 {} | 距 {} | 精排分 {}",
        log_prefix,
        iteration + 1,
        mode,
        recall_n,
        after_rank_len,
        len(results),
        dist_s,
        rr_s,
    )
    logger.debug(
        "{} 明细 k={} final_top_k={} llm_ref_k={} 距={} 分={}",
        log_prefix,
        k,
        final_top_k,
        llm_ref_k if llm_ref_k is not None else "-",
        [round(d, 4) for d in distances] if distances else [],
        [round(s, 4) for s in rerank_scores] if rerank_scores else [],
    )

    retrieved_docs = []
    for r in results:
        meta = {
            "document_id": r["document_id"],
            "document_title": title_map.get(r["document_id"], "未知文档"),
            "chunk_index": r["chunk_index"],
            "score": r.get("distance"),
        }
        if r.get("rerank_score") is not None:
            meta["rerank_score"] = r["rerank_score"]
        retrieved_docs.append({"content": r["chunk_text"], "metadata": meta})
    parts = []
    for doc in retrieved_docs:
        title = doc.get("metadata", {}).get("document_title", "未知文档")
        parts.append("【文档：%s】\n%s" % (title, doc["content"]))
    context = "\n\n".join(parts) if parts else ""

    return {
        "retrieved_docs": retrieved_docs,
        "context": context or "（未检索到相关文档，请确保文档库中有内容并已建立索引）",
    }
