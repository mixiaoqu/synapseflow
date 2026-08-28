"""Common retrieval helpers shared by KB workflows."""

from __future__ import annotations

from typing import Any, Mapping


def pick_query_from_state(
    state: Mapping[str, Any],
    *keys: str,
    default: str = "",
) -> str:
    """Pick the first non-empty query-like field from workflow state."""

    for key in keys:
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


async def run_state_kb_retrieval(
    state: Mapping[str, Any],
    *,
    query: str,
    log_prefix: str = "[KB Retrieval]",
) -> dict[str, Any]:
    """Run KB retrieval using the shared runtime context."""

    from app.services.kb_text_retrieval import run_kb_text_retrieval

    return await run_kb_text_retrieval(
        query=query,
        team_id=state.get("team_id"),
        knowledge_base_id=state.get("knowledge_base_id"),
        category_id=state.get("category_id"),
        log_prefix=log_prefix,
        user_id=state.get("user_id"),
    )
