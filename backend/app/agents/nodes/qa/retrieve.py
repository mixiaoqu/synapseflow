"""检索节点：理解用户问题并从知识库检索"""
import asyncio
from typing import Dict, Any

from loguru import logger
from sqlalchemy import select

from app.agents.states import IterativeQAState
from app.core.config import settings
from app.core.config.registry import config_registry
from app.db.models import Document
from app.services.embedding import embed_query
from app.services.vector_store import search
from app.services.reranker import rerank
from app.db.session import AsyncSessionLocal

DEFAULT_USER_ID = 1


async def retrieve_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    检索节点：从 pgvector 向量库检索相关文档块
    支持 collection_id 限定检索范围
    首轮/迭代 k、最终条数见 config/embedding.yaml retrieval；不再按距离阈值过滤。
    """
    rag = config_registry.get_rag_config()["retrieval"]
    query = state.get("optimized_query") or state.get("query", "")
    iteration = state.get("iteration", 0)
    collection_id = state.get("collection_id")
    k = rag["k_iteration"] if iteration > 0 else rag["k_first"]
    final_top_k = rag["final_top_k"]
    llm_ref_k_raw = rag.get("llm_reference_top_k")
    llm_ref_k = int(llm_ref_k_raw) if llm_ref_k_raw is not None else None

    query_embedding = await asyncio.to_thread(embed_query, query)

    document_ids = None
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
        results = await search(db, query_embedding, k=k, document_ids=document_ids)

    recall_n = len(results)
    rerank_applied = False
    if settings.RERANK_ENABLED and len(results) > 0:
        logger.debug("[QA检索] Rerank 候选=%s条 final_top_k=%s", len(results), final_top_k)
        results = await rerank(query, results, top_k=final_top_k)
        rerank_applied = True
    else:
        logger.debug("[QA检索] 未精排或无召回，截断为前%s条", final_top_k)
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
    logger.info(
        "[QA检索] round={} k={} 召回={}条 精排={} 精排后={}条 入上下文={}条 final_top_k={} llm_ref_k={} distance={} rerank_score={}",
        iteration + 1,
        k,
        recall_n,
        rerank_applied,
        after_rank_len,
        len(results),
        final_top_k,
        llm_ref_k if llm_ref_k is not None else "-",
        [round(d, 4) for d in distances] if distances else "[]",
        [round(s, 4) for s in rerank_scores] if rerank_scores else "-",
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
        parts.append(f"【文档：{title}】\n{doc['content']}")
    context = "\n\n".join(parts) if parts else ""

    return {
        "retrieved_docs": retrieved_docs,
        "context": context or "（未检索到相关文档，请确保文档库中有内容并已建立索引）",
    }
