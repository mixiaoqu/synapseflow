"""Response node for top-level agent orchestration."""

from __future__ import annotations

from typing import Any, Callable

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import get_optional_stream_writer
from app.agents.nodes.agent_orchestration.constants import (
    EXECUTION_ROUTE_TYPES,
    ROUTE_APPROVAL,
    ROUTE_CLARIFY_MAIN,
    ROUTE_DIRECT_RESPONSE,
    ROUTE_SAFE_BLOCK,
    ROUTE_UNSUPPORTED,
)
from app.agents.nodes.agent_orchestration.utils import (
    coerce_text,
    get_answer_llm,
    json_block,
)
from app.agents.nodes.kb_chat.answer import KB_OUT_OF_SCOPE_REPLY
from app.agents.prompts.kb_chat import build_page_context_block
from app.agents.states import AgentState
from app.services.chat_memory import format_chat_history


def build_direct_response_prompt(state: dict[str, Any]) -> str:
    classification = dict(state.get("classification") or {})
    intent = dict(classification.get("intent") or {})
    history = format_chat_history(
        list(state.get("chat_history") or []),
        max_messages=8,
        max_chars=12000,
        max_message_chars=3000,
    )
    memory_summary = str(state.get("memory_summary") or "").strip()[:4000]
    return f"""
你是面向用户的通用对话回答节点。请根据助手配置、当前问题和会话上下文直接回答用户。

你可以完成寒暄、写作、改写、翻译、总结、比较、逻辑推理、会话回顾和上下文延续。
不要提及工作流、Prompt、节点名或内部实现。默认使用自然清晰的中文回答。

助手名称：
{state.get("assistant_name") or "智能助手"}

助手人设：
{state.get("assistant_persona_prompt") or "(none)"}

助手回复规则：
{state.get("assistant_rule_template") or "(none)"}

页面上下文：
{build_page_context_block(
    page_config=dict(state.get("page_config") or {}),
    page_context=dict(state.get("page_context") or {}),
)}

最近 8 条对话：
{history or "(none)"}

更早对话概要：
{memory_summary or "(none)"}

用户当前问题：
{state.get("normalized_query") or state.get("query") or ""}

已解析目标：
{intent.get("goal") or ""}
""".strip()


def build_synthesized_response_prompt(state: dict[str, Any]) -> str:
    classification = dict(state.get("classification") or {})
    intent = dict(classification.get("intent") or {})
    synthesized_result = dict(state.get("synthesized_result") or {})
    return f"""
你是面向用户的最终回答节点。请根据助手配置和下方平台级结果回答用户。

核心规则：
- 只能使用“平台级结果”中的事实回答，不得补造知识、业务对象、字段值、排名、统计结果或接口返回值。
- 当结果显示知识库无命中时，明确说明当前知识库没有找到相关内容，不要自行扩展。
- 当结果显示业务子智能体失败、参数不足、未绑定工具或请求不支持时，准确说明业务查询未完成的原因或需要补充的信息。
- 不要把业务工具、数据库查询或业务接口问题说成“知识库没有提供工具”；知识库结果和业务子智能体结果必须分开表述。
- 可以根据助手人设和回复规则调整语气、格式和详略，但不得改变材料事实。
- 不要提及工作流、子图、工具配置、Prompt、节点名或内部实现。
- 默认使用自然清晰的中文回答。

助手名称：
{state.get("assistant_name") or "智能助手"}

助手人设：
{state.get("assistant_persona_prompt") or "(none)"}

助手回复规则：
{state.get("assistant_rule_template") or "(none)"}

页面上下文：
{build_page_context_block(
    page_config=dict(state.get("page_config") or {}),
    page_context=dict(state.get("page_context") or {}),
)}

用户原始问题：
{state.get("normalized_query") or state.get("query") or ""}

已解析目标：
{intent.get("goal") or ""}

平台级结果：
{json_block(synthesized_result)}
""".strip()


def build_non_execution_answer(state: dict[str, Any]) -> tuple[str, str]:
    route_type = str((state.get("route") or {}).get("route_type") or "").strip()
    classification = dict(state.get("classification") or {})
    intent = dict(classification.get("intent") or {})
    goal = str(intent.get("goal") or state.get("normalized_query") or "").strip()
    if route_type == ROUTE_CLARIFY_MAIN:
        if goal:
            return f"为了继续处理“{goal}”，请补充必要的信息。", "clarification_needed"
        return "请补充你想咨询或处理的具体问题。", "clarification_needed"
    if route_type == ROUTE_APPROVAL:
        return "这个请求需要先完成确认或审批后才能继续处理。", "approval_required"
    if route_type == ROUTE_SAFE_BLOCK:
        return "抱歉，当前请求命中安全或合规限制，无法继续处理。", "blocked"
    if route_type == ROUTE_UNSUPPORTED:
        return KB_OUT_OF_SCOPE_REPLY, "out_of_scope"
    return "抱歉，当前请求无法继续处理。", "failed"


def build_respond_node(*, answer_llm_factory: Callable[[], Any] | None):
    async def respond_node(state: AgentState) -> dict[str, Any]:
        route_type = str((state.get("route") or {}).get("route_type") or "").strip()
        writer = get_optional_stream_writer()
        retrieved_docs = list(state.get("retrieved_docs") or [])
        if route_type == ROUTE_DIRECT_RESPONSE:
            llm = get_answer_llm(state, answer_llm_factory)
            parts: list[str] = []
            async for chunk in llm.astream(build_direct_response_prompt(state)):
                text = coerce_text(getattr(chunk, "content", None))
                if not text:
                    continue
                parts.append(text)
                if writer is not None:
                    writer({"workflow_id": "agent", "node_id": "respond", "text": text})
            answer = "".join(parts).strip() or "抱歉，当前没有生成有效回答。"
            answer_status = "answered" if parts else "generation_failed"
        elif route_type in EXECUTION_ROUTE_TYPES:
            llm = get_answer_llm(state, answer_llm_factory)
            parts = []
            async for chunk in llm.astream(build_synthesized_response_prompt(state)):
                text = coerce_text(getattr(chunk, "content", None))
                if not text:
                    continue
                parts.append(text)
                if writer is not None:
                    writer({"workflow_id": "agent", "node_id": "respond", "text": text})
            answer = "".join(parts).strip() or "抱歉，当前没有生成有效回答。"
            answer_status = (
                str((state.get("synthesized_result") or {}).get("answer_status") or "answered")
                if parts
                else "generation_failed"
            )
        else:
            answer, answer_status = build_non_execution_answer(state)
            if writer is not None and answer:
                writer({"workflow_id": "agent", "node_id": "respond", "text": answer})

        response = {
            "answer": answer,
            "answer_status": answer_status or "answered",
            "citations": retrieved_docs,
        }
        log_node_info(
            workflow_id="agent",
            node_id="respond",
            node_name="输出结果",
            details={
                "路由类型": route_type,
                "回答状态": response["answer_status"],
                "回答长度": len(response["answer"]),
                "引用数": len(response["citations"]),
            },
        )
        return {
            "answer": response["answer"],
            "answer_status": response["answer_status"],
            "retrieved_docs": retrieved_docs,
            "backend_citations": retrieved_docs,
            "response": response,
            "final_response": response,
        }

    return respond_node
