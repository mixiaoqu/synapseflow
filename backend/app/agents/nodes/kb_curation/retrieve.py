"""Retrieval node for admin-facing knowledge-base curation."""

from typing import Any, Dict

from app.agents.states import KbCurationState
from app.services.kb_retrieval import run_kb_retrieval


async def retrieve_node(state: KbCurationState) -> Dict[str, Any]:
    """Retrieve context for the current admin curation query."""
    query = state.get("optimized_query") or state.get("query", "")
    return await run_kb_retrieval(
        query=query,
        collection_id=state.get("collection_id"),
        iteration=state.get("iteration", 0),
        log_prefix="[KB Curation Retrieval]",
    )
