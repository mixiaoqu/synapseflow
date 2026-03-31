"""End-user knowledge-base answer generation helpers and node."""

from typing import Any, AsyncGenerator, Callable, Dict, Optional

from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt
from app.agents.states import KbChatState
from app.core.llm import get_llm_for_generation

KB_EMPTY_COLLECTION_REPLY = (
    "当前选择的集合下还没有可检索的文档，请先在“文档库”中上传文档并完成索引。"
)
KB_NO_HITS_REPLY = (
    "没有在知识库中检索到与问题直接相关的资料。可以换一个说法或关键词，"
    "或将检索范围设为“全部知识库”后再试。"
)


def should_skip_kb_llm(state: Dict[str, Any]) -> Optional[str]:
    """Return a fixed reply when retrieval yields nothing useful."""
    status = state.get("kb_retrieval_status")
    if status == "empty_collection":
        return KB_EMPTY_COLLECTION_REPLY
    if status == "no_hits":
        return KB_NO_HITS_REPLY
    if status == "ok":
        return None
    if not (state.get("retrieved_docs") or []):
        return KB_NO_HITS_REPLY
    return None


def _build_prompt(state: Dict[str, Any]) -> str:
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
    state: Dict[str, Any],
    *,
    llm_factory: Callable[[], Any] = get_llm_for_generation,
) -> str:
    fixed = should_skip_kb_llm(state)
    if fixed:
        return fixed

    llm = llm_factory()
    response = await llm.ainvoke(_build_prompt(state))
    return _coerce_text(getattr(response, "content", response))


async def stream_kb_chat_answer_text(
    state: Dict[str, Any],
    *,
    llm_factory: Callable[[], Any] = get_llm_for_generation,
) -> AsyncGenerator[str, None]:
    fixed = should_skip_kb_llm(state)
    if fixed:
        yield fixed
        return

    llm = llm_factory()
    async for chunk in llm.astream(_build_prompt(state)):
        text = _coerce_text(getattr(chunk, "content", None))
        if text:
            yield text


async def user_kb_generate_answer_node(state: KbChatState) -> Dict[str, Any]:
    text = await generate_kb_chat_answer_text(state)
    return {
        "answer": text,
        "messages": [{"role": "assistant", "content": text}],
    }
