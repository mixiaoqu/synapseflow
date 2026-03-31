"""用户知识库：检索节点（共用向量检索，日志前缀区分场景）"""
from typing import Dict, Any

from app.agents.states import KbChatState
from app.services.kb_retrieval import run_kb_retrieval


async def user_kb_retrieve_node(state: KbChatState) -> Dict[str, Any]:
    """按用户原问题检索，不使用管理员侧的 query 优化字段。"""
    q = (state.get("query") or "").strip()
    return await run_kb_retrieval(
        query=q,
        collection_id=state.get("collection_id"),
        iteration=0,
        log_prefix="[用户知识库检索]",
    )
