"""Retrieval node for admin-facing knowledge-base curation."""

from typing import Any, Dict

from app.agents.common.retrieval import pick_query_from_state, run_state_kb_retrieval
from app.agents.states import KbCurationState


async def retrieve_node(state: KbCurationState) -> Dict[str, Any]:
    """Retrieve context for the current admin curation query."""

    query = pick_query_from_state(state, "optimized_query", "query")
    return await run_state_kb_retrieval(
        state,
        query=query,
        iteration=state.get("iteration", 0),
        log_prefix="[KB Curation Retrieval]",
    )
