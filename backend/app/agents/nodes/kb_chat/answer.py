"""Answer node for knowledge-base chat."""

from __future__ import annotations

from time import perf_counter
from typing import Any, AsyncGenerator, Callable

from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt, build_page_context_block
from app.agents.states import KnowledgeQaState
from app.core.llm import get_llm
from app.services.chat_memory import format_chat_history

KB_CHITCHAT_REPLY = (
    "你好，我可以基于当前知识库内容为你解答问题。"
)
KB_OUT_OF_SCOPE_REPLY = (
    "这个问题超出了当前知识库问答范围。请尽量询问已经收录到知识库中的内容。"
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


def _extract_usage_output_tokens(payload: Any) -> int | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        for key in ("output_tokens", "completion_tokens"):
            value = payload.get(key)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                pass
        usage = payload.get("usage")
        if usage is not None:
            return _extract_usage_output_tokens(usage)
    else:
        for key in ("output_tokens", "completion_tokens"):
            value = getattr(payload, key, None)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                pass
        usage = getattr(payload, "usage", None)
        if usage is not None:
            return _extract_usage_output_tokens(usage)
        response_metadata = getattr(payload, "response_metadata", None)
        if response_metadata is not None:
            return _extract_usage_output_tokens(response_metadata)
    return None


def _estimate_output_tokens(text: str) -> int:
    normalized = str(text or "").strip()
    if not normalized:
        return 0
    # 粗略估算：中文约 1 字/Token，英文及混合文本按 4 字符/Token 估算。
    ascii_chars = sum(1 for char in normalized if ord(char) < 128)
    non_ascii_chars = len(normalized) - ascii_chars
    return non_ascii_chars + max(1, ascii_chars // 4)


def _template_answer(state: dict[str, Any]) -> tuple[str | None, str | None]:
    question_type = str(state.get("question_type") or "").strip().lower()
    if question_type == "chitchat":
        return KB_CHITCHAT_REPLY, "chitchat"
    if question_type == "out_of_scope":
        return KB_OUT_OF_SCOPE_REPLY, "out_of_scope"
    return None, None


def _build_prompt(state: dict[str, Any]) -> str:
    return build_kb_chat_answer_prompt(
        query=state.get("query", ""),
        assistant_name=state.get("assistant_name") or "",
        assistant_persona_prompt=state.get("assistant_persona_prompt") or "",
        assistant_rule_template=state.get("assistant_rule_template") or "",
        page_context=build_page_context_block(
            page_config=dict(state.get("page_config") or {}),
            page_context=dict(state.get("page_context") or {}),
        ),
        chat_history_text=format_chat_history(state.get("chat_history") or [], max_messages=6),
        memory_summary=state.get("memory_summary") or "",
        evidence_status="sufficient",
        primary_context=state.get("primary_context") or "",
        supporting_context=state.get("supporting_context") or "",
    )


def _get_default_llm(state: dict[str, Any]) -> Any:
    model_key = str(state.get("assistant_llm_model_key") or "generation").strip() or "generation"
    return get_llm(model_key)


async def build_kb_chat_answer_text(
    state: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    fixed, _status = _template_answer(state)
    if fixed is not None:
        return fixed, {
            "first_token_latency_ms": 0,
            "output_tokens": _estimate_output_tokens(fixed),
            "output_chars": len(fixed),
            "streamed": False,
        }
    llm = llm_factory() if llm_factory is not None else _get_default_llm(state)
    response = await llm.ainvoke(_build_prompt(state))
    answer_text = _coerce_text(getattr(response, "content", response))
    usage_output_tokens = _extract_usage_output_tokens(response)
    return answer_text, {
        "first_token_latency_ms": None,
        "output_tokens": (
            usage_output_tokens
            if usage_output_tokens is not None
            else _estimate_output_tokens(answer_text)
        ),
        "output_chars": len(answer_text),
        "streamed": False,
    }


async def stream_kb_chat_answer_text(
    state: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
    stream_writer: Callable[[dict[str, Any]], None] | None = None,
    workflow_id: str = "knowledge_qa",
    node_id: str = "compose_answer",
) -> AsyncGenerator[dict[str, Any], None]:
    fixed, _status = _template_answer(state)
    if fixed is not None:
        if stream_writer is not None:
            stream_writer({"workflow_id": workflow_id, "node_id": node_id, "text": fixed})
        yield {"type": "text", "text": fixed}
        return

    llm = llm_factory() if llm_factory is not None else _get_default_llm(state)
    emit_activity(
        stream_writer,
        workflow_id=workflow_id,
        node_id=node_id,
        stage="answer_stream",
        message="正在组织最终回答",
        display_stage="compose",
        display_title="💡 总结最终结果",
        activity_text="正在组织最终回复",
        context_len=len(state.get("context") or ""),
        retrieved_count=len(state.get("retrieved_docs") or []),
    )
    usage_output_tokens: int | None = None
    async for chunk in llm.astream(_build_prompt(state)):
        text = _coerce_text(getattr(chunk, "content", None))
        if text:
            if stream_writer is not None:
                stream_writer({"workflow_id": workflow_id, "node_id": node_id, "text": text})
            yield {"type": "text", "text": text}
        usage_output_tokens = _extract_usage_output_tokens(chunk) or usage_output_tokens
    yield {"type": "meta", "output_tokens": usage_output_tokens}


def _resolve_status(state: dict[str, Any]) -> str:
    fixed, fixed_status = _template_answer(state)
    if fixed is not None and fixed_status is not None:
        return fixed_status
    return "answered"


def build_kb_chat_answer_node(
    *,
    llm_factory: Callable[[], Any] | None = None,
    workflow_id: str = "knowledge_qa",
    node_id: str = "compose_answer",
) -> Callable[[KnowledgeQaState], Any]:
    async def _node(state: KnowledgeQaState) -> dict[str, Any]:
        stream_writer = get_optional_stream_writer()
        started_at = perf_counter()
        fixed, _fixed_status = _template_answer(state)
        parts: list[str] = []
        output_tokens: int | None = None
        first_token_latency_ms: int | None = 0 if fixed is not None else None

        if fixed is not None:
            answer = fixed
            output_tokens = _estimate_output_tokens(answer)
        else:
            async for item in stream_kb_chat_answer_text(
                state,
                llm_factory=llm_factory,
                stream_writer=stream_writer,
                workflow_id=workflow_id,
                node_id=node_id,
            ):
                if item.get("type") == "text":
                    text = str(item.get("text") or "")
                    if text and first_token_latency_ms is None:
                        first_token_latency_ms = int((perf_counter() - started_at) * 1000)
                    if text:
                        parts.append(text)
                elif item.get("type") == "meta":
                    raw_tokens = item.get("output_tokens")
                    try:
                        output_tokens = int(raw_tokens) if raw_tokens is not None else output_tokens
                    except (TypeError, ValueError):
                        pass
            answer = "".join(parts)

        status = _resolve_status({**state, "answer": answer})
        total_latency_ms = int((perf_counter() - started_at) * 1000)
        return {
            "answer": answer,
            "answer_status": status,
            "messages": [{"role": "assistant", "content": answer}],
            "answer_trace": {
                "latency_ms": total_latency_ms,
                "first_token_latency_ms": first_token_latency_ms,
                "output_tokens": (
                    output_tokens
                    if output_tokens is not None
                    else _estimate_output_tokens(answer)
                ),
                "output_chars": len(answer),
            },
        }

    return _node
