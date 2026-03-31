"""Routing helpers for admin-facing knowledge-base curation."""

from app.agents.states import KbCurationState


def should_continue_iteration(state: KbCurationState) -> str:
    """Route to the next optimization round or finish the workflow."""
    return "query_optimizer" if state.get("should_continue") else "end"
