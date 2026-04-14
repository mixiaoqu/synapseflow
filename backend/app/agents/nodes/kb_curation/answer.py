"""Answer generation node for admin-facing knowledge-base curation."""

from typing import Any, Dict

from app.agents.nodes.kb_chat.generate_answer import should_skip_kb_llm
from app.agents.prompts import build_kb_curation_answer_prompt
from app.agents.states import KbCurationState
from app.core.llm import get_llm_for_generation


async def answer_node(state: KbCurationState) -> Dict[str, Any]:
    """Generate an answer for the current admin curation round."""
    fixed = should_skip_kb_llm(state)
    if fixed:
        return {
            "answer": fixed,
            "messages": [{"role": "assistant", "content": fixed}],
        }

    llm = get_llm_for_generation()
    query = state.get("optimized_query") or state.get("query", "")
    iteration = state.get("iteration", 0)
    last_feedback = state.get("last_evaluation_feedback")
    prompt = build_kb_curation_answer_prompt(
        query=query,
        context=state.get("context", ""),
        iteration=iteration,
        last_feedback=last_feedback,
    )

    response = await llm.ainvoke(prompt)

    return {
        "answer": response.content,
        "messages": [{"role": "assistant", "content": response.content}],
    }
