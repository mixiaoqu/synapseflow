"""
问答相关工具

供 QA 图节点调用，或绑定给 LLM 实现 ReAct 模式。
"""
import asyncio
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import select

from app.db.models import Document
from app.db.session import AsyncSessionLocal
from app.services.embedding import embed_query
from app.services.vector_store import search
from app.services.reranker import rerank as rerank_service
from app.core.config import settings
from app.core.config.registry import config_registry

DEFAULT_USER_ID = 1


@tool
async def search_knowledge_base(
    query: str,
    k: int = 5,
    collection_id: Optional[int] = None,
) -> str:
    """根据问题从知识库检索相关文档片段。query: 用户问题；k: 返回条数；collection_id: 限定集合（可选）。"""
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
                return "（该集合暂无已索引文档，请先上传并建立索引）"

    async with AsyncSessionLocal() as db:
        results = await search(db, query_embedding, k=k, document_ids=document_ids)

    if not results:
        return "（未检索到相关文档，请确保文档库中有内容并已建立索引）"

    chunks = [
        {"chunk_text": r["chunk_text"], "document_id": r["document_id"], "chunk_index": r["chunk_index"], "distance": r.get("distance")}
        for r in results
    ]

    final_top_k = config_registry.get_rag_config()["retrieval"]["final_top_k"]
    if settings.RERANK_ENABLED and len(chunks) > final_top_k:
        chunks = await rerank_service(query, chunks, top_k=final_top_k)
    else:
        chunks = chunks[:final_top_k]

    return "\n\n".join(c["chunk_text"] for c in chunks)


@tool
async def rerank_documents(
    query: str,
    documents: list[str],
    top_k: int = 5,
) -> list[str]:
    """对文档列表按与问题的相关度重排，返回 top_k 条。"""
    if not documents:
        return []
    chunks = [
        {"chunk_text": d, "document_id": 0, "chunk_index": i, "distance": 0.0}
        for i, d in enumerate(documents)
    ]
    reranked = await rerank_service(query, chunks, top_k=top_k)
    return [r["chunk_text"] for r in reranked]
