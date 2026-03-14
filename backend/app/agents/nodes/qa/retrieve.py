"""检索节点：理解用户问题并从知识库检索"""
import asyncio
from typing import Dict, Any

from app.agents.states import IterativeQAState
from app.services.embedding import embed_query
from app.services.vector_store import search
from app.db.session import AsyncSessionLocal


async def retrieve_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    检索节点：从 pgvector 向量库检索相关文档块
    迭代时增加召回数 k（5 -> 8）
    """
    # 优先使用优化后的问题进行检索
    query = state.get("optimized_query") or state.get("query", "")
    iteration = state.get("iteration", 0)
    k = 8 if iteration > 0 else 5  # 迭代时增加召回

    # embed_query 为同步调用，放入线程池避免阻塞
    query_embedding = await asyncio.to_thread(embed_query, query)

    async with AsyncSessionLocal() as db:
        results = await search(db, query_embedding, k=k)

    retrieved_docs = [
        {
            "content": r["chunk_text"],
            "metadata": {"document_id": r["document_id"], "chunk_index": r["chunk_index"], "score": r.get("distance")},
        }
        for r in results
    ]
    context = "\n\n".join([doc["content"] for doc in retrieved_docs])

    return {
        "retrieved_docs": retrieved_docs,
        "context": context or "（未检索到相关文档，请确保文档库中有内容并已建立索引）",
    }
