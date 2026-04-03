"""End-user knowledge-base answer generation helpers and node."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Callable, Optional

from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt
from app.agents.states import KbChatState

KB_EMPTY_COLLECTION_REPLY = (
    "The selected knowledge base does not have any indexed documents yet. "
    "Please upload documents and finish indexing first."
)
KB_NO_HITS_REPLY = (
    "I could not find directly relevant material in the knowledge base. "
    "Try rephrasing the question or widening the retrieval scope."
)


def _get_default_llm_factory() -> Callable[[], Any]:
    from app.core.llm import get_llm_for_generation

    return get_llm_for_generation


def should_skip_kb_llm(state: dict[str, Any]) -> Optional[str]:
    """Return a fixed reply when retrieval yields nothing useful."""

    status = state.get("kb_retrieval_status")
    if status in {"empty_collection", "empty_knowledge_base"}:
        return KB_EMPTY_COLLECTION_REPLY
    if status == "no_hits":
        return KB_NO_HITS_REPLY
    if status == "ok":
        return None
    if not (state.get("retrieved_docs") or []):
        return KB_NO_HITS_REPLY
    return None


def _build_prompt(state: dict[str, Any]) -> str:
    return build_kb_chat_answer_prompt(
        state.get("query", ""),
        state.get("context", ""),
    )


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content or "")


async def generate_kb_chat_answer_text(
    state: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> str:
    fixed = should_skip_kb_llm(state)
    if fixed:
        return fixed

    resolved_llm_factory = llm_factory or _get_default_llm_factory()
    llm = resolved_llm_factory()
    response = await llm.ainvoke(_build_prompt(state))
    return _coerce_text(getattr(response, "content", response))


async def stream_kb_chat_answer_text(
    state: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> AsyncGenerator[str, None]:
    fixed = should_skip_kb_llm(state)
    if fixed:
        yield fixed
        return

    resolved_llm_factory = llm_factory or _get_default_llm_factory()
    llm = resolved_llm_factory()
    async for chunk in llm.astream(_build_prompt(state)):
        text = _coerce_text(getattr(chunk, "content", None))
        if text:
            yield text


async def user_kb_generate_answer_node(state: KbChatState) -> dict[str, Any]:
    text = await generate_kb_chat_answer_text(state)
    return {
        "answer": text,
        "messages": [{"role": "assistant", "content": text}],
    }
