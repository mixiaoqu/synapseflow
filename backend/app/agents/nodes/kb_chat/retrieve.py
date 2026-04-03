"""Retrieval node for end-user knowledge-base chat."""

from typing import Any, Dict

from app.agents.common.retrieval import pick_query_from_state, run_state_kb_retrieval
from app.agents.states import KbChatState


async def user_kb_retrieve_node(state: KbChatState) -> Dict[str, Any]:
    """Retrieve context for the current user query."""

    query = pick_query_from_state(state, "query")
    return await run_state_kb_retrieval(
        state,
        query=query,
        iteration=0,
        log_prefix="[User KB Retrieval]",
    )
