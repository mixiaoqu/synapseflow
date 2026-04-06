"""QA-related reusable tools."""

from typing import Optional

from langchain_core.tools import tool

from app.services.kb_retrieval import run_kb_retrieval
from app.services.reranker import rerank as rerank_service


@tool
async def search_knowledge_base(
    query: str,
    k: int = 5,
    knowledge_base_id: Optional[int] = None,
    category_id: Optional[int] = None,
) -> str:
    """Search the KB and return the top chunk texts."""
    result = await run_kb_retrieval(
        query=query,
        knowledge_base_id=knowledge_base_id,
        category_id=category_id,
        result_limit=max(1, k),
        context_budget=0,
        log_prefix="[QA Tool Retrieval]",
    )
    docs = result.get("retrieved_docs") or []
    if not docs:
        return result.get("context", "(No relevant documents found)")
    return "\n\n".join((doc.get("content") or "").strip() for doc in docs if doc.get("content"))
