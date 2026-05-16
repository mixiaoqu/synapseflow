"""End-user knowledge-base answer generation helpers and node."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Callable, Optional

from loguru import logger

from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt
from app.agents.states import KbChatState
from app.services.chat_memory import format_chat_history

KB_EMPTY_COLLECTION_REPLY = (
    "The selected knowledge base does not have any indexed documents yet. "
    "Please upload documents and finish indexing first."
)
KB_NO_HITS_REPLY = (
    "I could not find directly relevant material in the knowledge base. "
    "Try rephrasing the question or widening the retrieval scope."
)
KB_CHITCHAT_GREETING_REPLY = (
    "你好，我主要负责回答当前知识库中的制度、流程、规则和文档内容。你可以继续问我相关问题。"
)
KB_CHITCHAT_THANKS_REPLY = "不客气，我可以继续帮你查询当前知识库里的内容。"
KB_CHITCHAT_GENERIC_REPLY = (
    "你好，我主要负责回答当前知识库相关问题，例如制度、流程、规则和文档内容。你可以继续问我相关问题。"
)
KB_OUT_OF_SCOPE_REPLY = (
    "我主要负责回答当前知识库相关问题，例如制度、流程、规则和文档内容。"
    "当前这个请求不属于知识库问答范围，你可以继续问我知识库里的内容。"
)


def _get_default_llm(state: dict[str, Any]) -> Any:
    from app.core.llm import get_llm

    model_key = str(state.get("assistant_llm_model_key") or "generation").strip() or "generation"
    return get_llm(model_key)


def _response_mode(state: dict[str, Any]) -> str:
    retrieval_plan = state.get("retrieval_plan") or {}
    answer_plan = retrieval_plan.get("answer") or {}
    return str(answer_plan.get("response_mode") or "").strip().lower()


def should_skip_kb_llm(state: dict[str, Any]) -> Optional[str]:
    """Return a fixed reply when retrieval yields nothing useful."""

    return should_skip_kb_llm_with_options(state, include_retrieval_fallback=True)


def should_skip_kb_llm_with_options(
    state: dict[str, Any],
    *,
    include_retrieval_fallback: bool,
) -> Optional[str]:
    """Optionally short-circuit when retrieval yields nothing useful."""

    response_mode = _response_mode(state)
    if response_mode == "out_of_scope":
        return KB_OUT_OF_SCOPE_REPLY
    if response_mode == "chitchat":
        query = str(state.get("query") or "").strip().lower()
        if any(token in query for token in ("谢谢", "感谢", "thanks", "thank you")):
            return KB_CHITCHAT_THANKS_REPLY
        if any(
            token in query
            for token in (
                "你好",
                "您好",
                "早上好",
                "上午好",
                "中午好",
                "下午好",
                "晚上好",
                "hi",
                "hello",
                "hey",
            )
        ):
            return KB_CHITCHAT_GREETING_REPLY
        return KB_CHITCHAT_GENERIC_REPLY

    status = state.get("kb_retrieval_status")
    if include_retrieval_fallback and status in {"empty_collection", "empty_knowledge_base"}:
        return KB_EMPTY_COLLECTION_REPLY
    if include_retrieval_fallback and status == "no_hits":
        return KB_NO_HITS_REPLY
    if status == "ok":
        return None
    if include_retrieval_fallback and not (state.get("retrieved_docs") or []):
        return KB_NO_HITS_REPLY
    return None


def _build_prompt(state: dict[str, Any]) -> str:
    return build_kb_chat_answer_prompt(
        state.get("query", ""),
        state.get("context", ""),
        chat_history_text=format_chat_history(state.get("chat_history") or [], max_messages=6),
        memory_summary=state.get("memory_summary") or "",
        assistant_name=state.get("assistant_name") or "",
        assistant_welcome_message=state.get("assistant_welcome_message") or "",
        assistant_placeholder_text=state.get("assistant_placeholder_text") or "",
        assistant_persona_prompt=state.get("assistant_persona_prompt") or "",
        assistant_rule_template=state.get("assistant_rule_template") or "",
        assistant_suggested_prompts=list(state.get("assistant_suggested_prompts") or []),
        page_config=dict(state.get("page_config") or {}),
        page_context=dict(state.get("page_context") or {}),
        evidence_status=state.get("kb_retrieval_status") or "ok",
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
    fixed = should_skip_kb_llm_with_options(state, include_retrieval_fallback=False)
    if fixed:
        return fixed

    llm = llm_factory() if llm_factory is not None else _get_default_llm(state)
    prompt = _build_prompt(state)
    stream_writer = get_optional_stream_writer()
    emit_progress(
        stream_writer,
        node_id="answer",
        stage="answer_prepare",
        message="正在组织回答...",
        context_len=len(state.get("context") or ""),
        retrieved_count=len(state.get("retrieved_docs") or []),
    )
    try:
        logger.info(
            "[KB Answer] invoking LLM | query_len={} context_len={} retrieved_count={}",
            len(state.get("query") or ""),
            len(state.get("context") or ""),
            len(state.get("retrieved_docs") or []),
        )
        response = await llm.ainvoke(prompt)
        return _coerce_text(getattr(response, "content", response))
    except Exception as exc:
        logger.exception(
            "[KB Answer] LLM invoke failed | query_len={} context_len={} retrieved_count={} error={}",
            len(state.get("query") or ""),
            len(state.get("context") or ""),
            len(state.get("retrieved_docs") or []),
            exc,
        )
        raise


async def stream_kb_chat_answer_text(
    state: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
    stream_writer: Callable[[dict[str, Any]], None] | None = None,
) -> AsyncGenerator[str, None]:
    fixed = should_skip_kb_llm_with_options(state, include_retrieval_fallback=False)
    if fixed:
        if stream_writer is not None:
            stream_writer({"node_id": "answer", "text": fixed})
        yield fixed
        return

    llm = llm_factory() if llm_factory is not None else _get_default_llm(state)
    prompt = _build_prompt(state)
    emit_progress(
        stream_writer,
        node_id="answer",
        stage="answer_stream",
        message="正在生成回答...",
        context_len=len(state.get("context") or ""),
        retrieved_count=len(state.get("retrieved_docs") or []),
    )
    logger.info(
        "[KB Answer] streaming LLM | query_len={} context_len={} retrieved_count={}",
        len(state.get("query") or ""),
        len(state.get("context") or ""),
        len(state.get("retrieved_docs") or []),
    )
    try:
        async for chunk in llm.astream(prompt):
            text = _coerce_text(getattr(chunk, "content", None))
            if text:
                if stream_writer is not None:
                    stream_writer({"node_id": "answer", "text": text})
                yield text
    except Exception as exc:
        logger.exception(
            "[KB Answer] LLM stream failed | query_len={} context_len={} retrieved_count={} error={}",
            len(state.get("query") or ""),
            len(state.get("context") or ""),
            len(state.get("retrieved_docs") or []),
            exc,
        )
        raise


def build_user_kb_generate_answer_node(
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> Callable[[KbChatState], Any]:
    """Build an answer node that can emit token chunks through LangGraph custom streams."""

    async def _node(state: KbChatState) -> dict[str, Any]:
        parts: list[str] = []
        stream_writer = get_optional_stream_writer()
        async for text in stream_kb_chat_answer_text(
            state,
            llm_factory=llm_factory,
            stream_writer=stream_writer,
        ):
            parts.append(text)

        answer = "".join(parts)
        return {
            "answer": answer,
            "messages": [{"role": "assistant", "content": answer}],
        }

    return _node


async def user_kb_generate_answer_node(state: KbChatState) -> dict[str, Any]:
    return await build_user_kb_generate_answer_node()(state)
