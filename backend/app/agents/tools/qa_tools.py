"""QA-related reusable tools."""

from typing import Optional

from langchain_core.tools import tool

from app.services.kb_retrieval import run_kb_retrieval
from app.services.reranker import rerank as rerank_service


@tool
async def search_knowledge_base(
    query: str,
    k: int = 5,
    collection_id: Optional[int] = None,
) -> str:
    """Search the KB and return the top chunk texts."""
    result = await run_kb_retrieval(
        query=query,
        collection_id=collection_id,
        result_limit=max(1, k),
        context_budget=0,
        log_prefix="[QA Tool Retrieval]",
    )
    docs = result.get("retrieved_docs") or []
    if not docs:
        return result.get("context", "（未检索到相关文档）")
    return "\n\n".join((doc.get("content") or "").strip() for doc in docs if doc.get("content"))


@tool
async def rerank_documents(
    query: str,
    documents: list[str],
    top_k: int = 5,
) -> list[str]:
    """Rerank a list of candidate documents for a query."""
    if not documents:
        return []
    chunks = [
        {"chunk_text": doc, "document_id": 0, "chunk_index": idx, "distance": 0.0}
        for idx, doc in enumerate(documents)
    ]
    reranked = await rerank_service(query, chunks, top_k=top_k)
    return [row["chunk_text"] for row in reranked]
