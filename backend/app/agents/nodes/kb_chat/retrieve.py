"""Retrieval node for end-user knowledge-base chat."""

from typing import Any, Dict

from app.agents.states import KbChatState
from app.services.kb_retrieval import run_kb_retrieval


async def user_kb_retrieve_node(state: KbChatState) -> Dict[str, Any]:
    """Retrieve context for the current user query."""
    query = (state.get("query") or "").strip()
    return await run_kb_retrieval(
        query=query,
        knowledge_base_id=state.get("knowledge_base_id"),
        iteration=0,
        log_prefix="[User KB Retrieval]",
        user_id=state.get("user_id"),
    )
