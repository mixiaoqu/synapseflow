"""检索节点：理解用户问题并从知识库检索"""
from typing import Dict, Any

from app.agents.states import IterativeQAState
from app.services.kb_retrieval import run_kb_retrieval


async def retrieve_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    迭代 QA 检索：支持 optimized_query；实现见 services.kb_retrieval。
    """
    query = state.get("optimized_query") or state.get("query", "")
    return await run_kb_retrieval(
        query=query,
        collection_id=state.get("collection_id"),
        iteration=state.get("iteration", 0),
        log_prefix="[QA检索]",
    )
