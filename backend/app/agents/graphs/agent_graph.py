"""Top-level single-capability agent workflow graph."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.common.agent_intent import build_agent_decision
from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.nodes.kb_chat.answer import KB_OUT_OF_SCOPE_REPLY
from app.agents.prompts.kb_chat import build_page_context_block
from app.agents.runtime.capabilities import (
    CapabilityDefinition,
    get_capability_definition,
    get_capability_definitions,
)
from app.agents.runtime.factory import get_graph_definition
from app.agents.states import AgentState
from app.core.llm import get_llm
from app.services.chat_memory import format_chat_history

HANDOFF_TERMINAL_PUNCTUATION = "。.!！？?"


def _parse_stream_chunk(chunk: Any) -> tuple[str | None, dict[str, Any]]:
    if isinstance(chunk, tuple) and len(chunk) == 2:
        mode, data = chunk
        if isinstance(mode, str) and isinstance(data, dict):
            return mode, data
        return None, {}
    if isinstance(chunk, dict):
        chunk_type = chunk.get("type")
        chunk_data = chunk.get("data", {})
        if isinstance(chunk_type, str) and isinstance(chunk_data, dict):
            return chunk_type, chunk_data
    return None, {}


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content or "")


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, indent=2)


def _forward_subgraph_custom_event(
    writer: Callable[[dict[str, Any]], None] | None,
    workflow_id: str,
    data: dict[str, Any],
) -> None:
    if writer is None:
        return
    event_workflow_id = str(data.get("workflow_id") or "").strip()
    if not event_workflow_id:
        raise ValueError("Subgraph custom event is missing workflow_id")
    if event_workflow_id != workflow_id:
        raise ValueError(
            "Subgraph custom event workflow_id mismatch: "
            f"expected={workflow_id} actual={event_workflow_id}"
        )
    payload = dict(data)
    writer(payload)


def _emit_subgraph_node_complete(
    writer: Callable[[dict[str, Any]], None] | None,
    workflow_id: str,
    node_id: str,
    node_state: dict[str, Any],
) -> None:
    if writer is None:
        return
    writer(
        {
            "type": "node_complete",
            "workflow_id": workflow_id,
            "node_id": node_id,
            "node_state": node_state,
        }
    )


def _normalize_sentence(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().strip("“”\"'"))
    if not normalized:
        return ""
    normalized = normalized.rstrip("，,；;：: ")
    if normalized[-1] not in HANDOFF_TERMINAL_PUNCTUATION:
        normalized = f"{normalized}。"
    return normalized


def _format_handoff_message(goal: str, capability: CapabilityDefinition) -> str:
    normalized_goal = _normalize_sentence(goal).rstrip(HANDOFF_TERMINAL_PUNCTUATION)
    normalized_action = _normalize_sentence(capability.handoff_action or "")
    if not normalized_goal or not normalized_action:
        raise ValueError(
            f"Capability {capability.capability_id} cannot build a handoff message"
        )
    return f"明白，你想{normalized_goal}。我先{normalized_action}"


def _split_handoff_message(message: str) -> list[str]:
    chunks: list[str] = []
    current = ""
    for char in message:
        current += char
        if char in "，。！？,.!?\n" or len(current) >= 3:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def _stream_handoff_message(
    writer: Callable[[dict[str, Any]], None] | None,
    message: str,
) -> None:
    if writer is None:
        return
    for text in _split_handoff_message(f"{message}\n\n"):
        writer(
            {
                "workflow_id": "agent",
                "node_id": "invoke",
                "text": text,
                "phase": "handoff",
            }
        )


def _answer_starts_with_handoff(answer: str, handoff_message: str) -> bool:
    answer_key = re.sub(r"\s+", " ", str(answer or "").strip())
    handoff_key = re.sub(r"\s+", " ", str(handoff_message or "").strip())
    return bool(handoff_key) and answer_key.startswith(handoff_key)


def _unsupported_answer() -> tuple[str, str]:
    return KB_OUT_OF_SCOPE_REPLY, "out_of_scope"


def _knowledge_diagnostics(child_state: dict[str, Any]) -> dict[str, Any]:
    """Expose the bounded retrieval diagnostics consumed by chat logging."""

    if not child_state.get("retrieval_analysis"):
        return {}
    retrieval_analysis = dict(child_state.get("retrieval_analysis") or {})
    return {
        "question_type": child_state.get("question_type"),
        "retrieval_complexity": child_state.get("retrieval_complexity"),
        "route_reason": retrieval_analysis.get("reason"),
        "retrieval_execution_plan": dict(
            child_state.get("retrieval_execution_plan") or {}
        ),
        "semantic_queries": list(child_state.get("semantic_queries") or []),
        "lexical_terms": list(child_state.get("lexical_terms") or []),
        "candidate_entities": list(child_state.get("candidate_entities") or []),
        "plan_trace": dict(child_state.get("plan_trace") or {}),
        "rewrite_trace": dict(child_state.get("rewrite_trace") or {}),
        "retrieval_trace": dict(child_state.get("retrieval_trace") or {}),
        "context": str(child_state.get("context") or ""),
    }


def _get_answer_llm(
    state: dict[str, Any],
    llm_factory: Callable[[], Any] | None,
) -> Any:
    if llm_factory is not None:
        return llm_factory()
    model_key = str(state.get("assistant_llm_model_key") or "generation").strip()
    return get_llm(model_key or "generation")


def _build_response_material_block(workflow_result: dict[str, Any]) -> str:
    workflow_id = str(workflow_result.get("workflow_id") or "").strip()
    evidence = dict(workflow_result.get("evidence") or {})
    data = dict(evidence.get("data") or {})
    if workflow_id == "knowledge_qa":
        return "\n".join(
            [
                "资料类型：知识库检索结果",
                f"结果状态：{workflow_result.get('status') or evidence.get('status') or ''}",
                "",
                "主资料：",
                str(data.get("primary_context") or "(none)"),
                "",
                "辅助资料：",
                str(data.get("supporting_context") or "(none)"),
                "",
                "检索元数据 JSON：",
                _json_block(workflow_result.get("payload") or {}),
            ]
        )
    if workflow_id == "business_ops":
        return "\n".join(
            [
                "资料类型：业务接口查询结果",
                f"结果状态：{workflow_result.get('status') or evidence.get('status') or ''}",
                "",
                "业务数据 JSON：",
                _json_block(data),
                "",
                "业务结果元数据 JSON：",
                _json_block(workflow_result.get("payload") or {}),
            ]
        )
    return "\n".join(
        ["资料类型：通用能力结果", "能力结果 JSON：", _json_block(workflow_result)]
    )


def _build_conversation_response_prompt(state: dict[str, Any]) -> str:
    decision = dict(state.get("decision") or {})
    intent = dict(decision.get("intent") or {})
    history = format_chat_history(
        list(state.get("chat_history") or []),
        max_messages=8,
        max_chars=12000,
        max_message_chars=3000,
    )
    memory_summary = str(state.get("memory_summary") or "").strip()[:4000]
    return f"""
你是面向用户的通用对话回答节点。请根据助手配置、当前问题和当前会话上下文直接回答用户。

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
{state.get("query") or ""}

已解析目标：
{intent.get("goal") or ""}
""".strip()


def _build_capability_response_prompt(state: dict[str, Any]) -> str:
    decision = dict(state.get("decision") or {})
    intent = dict(decision.get("intent") or {})
    workflow_result = dict(state.get("workflow_result") or {})
    return f"""
你是面向用户的最终回答节点。请根据助手配置和下方结构化材料回答用户。

核心规则：
- 只能使用“结构化材料”中的事实回答，不得补造知识、业务对象、字段值、排名、统计结果或接口返回值。
- 当材料显示知识库无命中时，明确说明当前知识库没有找到相关内容，不要自行扩展。
- 当材料显示业务接口失败、参数不足或请求不支持时，准确说明原因或需要补充的信息。
- 可以根据助手人设和回复规则调整语气、格式和详略，但不得改变材料事实。
- 不要提及工作流、子图、工具配置、Prompt、节点名或内部实现。
- 不要重复此前已经输出的过渡句。
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
{state.get("query") or ""}

已解析目标：
{intent.get("goal") or ""}

结构化材料：
{_build_response_material_block(workflow_result)}
""".strip()


def _build_final_response_prompt(state: dict[str, Any]) -> str:
    action = str((state.get("decision") or {}).get("action") or "").strip()
    if action == "respond":
        return _build_conversation_response_prompt(state)
    return _build_capability_response_prompt(state)


def create_agent_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the top-level single-capability workflow graph."""

    planner_factory = planner_llm_factory or llm_factory
    answer_factory = answer_llm_factory or llm_factory
    capabilities = get_capability_definitions()
    capability_graphs = {
        capability.capability_id: get_graph_definition(capability.graph_id).build(
            planner_llm_factory=planner_factory,
            answer_llm_factory=answer_factory,
        )
        for capability in capabilities
    }
    workflow = StateGraph(AgentState)

    async def _decide_node(state: AgentState) -> dict[str, Any]:
        writer = get_optional_stream_writer()
        emit_activity(
            writer,
            workflow_id="agent",
            node_id="decide",
            stage="decide",
            message="正在理解用户目标",
            display_stage="decide",
            display_title="理解问题",
            activity_text="结合上下文理解你的需求",
        )
        decision = await build_agent_decision(
            str(state.get("query") or ""),
            capabilities=capabilities,
            chat_history=list(state.get("chat_history") or []),
            memory_summary=state.get("memory_summary"),
            page_context=dict(state.get("page_context") or {}),
            llm_factory=planner_factory,
        )
        log_node_info(
            workflow_id="agent",
            node_id="decide",
            node_name="理解并决策",
            details={
                "处理动作": decision.get("action"),
                "意图类型": (decision.get("intent") or {}).get("kind"),
                "用户目标": (decision.get("intent") or {}).get("goal"),
                "能力ID": decision.get("capability_id"),
                "缺失字段": decision.get("missing_fields"),
                "判断原因": decision.get("reason"),
            },
        )
        emit_activity(
            writer,
            workflow_id="agent",
            node_id="decide",
            stage="decide",
            message="已理解用户目标",
            display_stage="decide",
            display_title="理解问题",
            activity_text="已明确当前请求的处理方向",
            activity_status="completed",
        )
        return {"decision": decision}

    async def _clarify_node(state: AgentState) -> dict[str, Any]:
        decision = dict(state.get("decision") or {})
        intent = dict(decision.get("intent") or {})
        missing_fields = list(decision.get("missing_fields") or [])
        goal = str(intent.get("goal") or "").strip()
        question = "请补充你想咨询或处理的具体问题。"
        if goal and missing_fields:
            question = f"为了继续处理“{goal}”，请补充必要的信息。"
        clarification = {
            "question": question,
            "missing_fields": missing_fields,
        }
        log_node_info(
            workflow_id="agent",
            node_id="clarify",
            node_name="请求澄清",
            details={"澄清问题": question, "缺失字段": missing_fields},
        )
        return {
            "clarification": clarification,
            "answer": question,
            "answer_status": "clarification_needed",
            "retrieved_docs": [],
            "backend_citations": [],
        }

    async def _invoke_node(state: AgentState) -> dict[str, Any]:
        decision = dict(state.get("decision") or {})
        capability_id = str(decision.get("capability_id") or "").strip()
        capability = get_capability_definition(capability_id)
        subgraph = capability_graphs.get(capability_id)
        if subgraph is None:
            raise RuntimeError(f"Capability graph is not initialized: {capability_id}")

        intent = dict(decision.get("intent") or {})
        handoff_message = (
            _format_handoff_message(str(intent.get("goal") or ""), capability)
            if capability.handoff_action
            else ""
        )
        writer = get_optional_stream_writer()
        if handoff_message:
            _stream_handoff_message(writer, handoff_message)
        child_input = capability.input_builder(state, decision)

        workflow_result: dict[str, Any] | None = None
        final_child_state: dict[str, Any] = {}
        async for chunk in subgraph.astream(
            child_input,
            stream_mode=["updates", "custom"],
            version="v2",
        ):
            chunk_type, chunk_data = _parse_stream_chunk(chunk)
            if chunk_type == "custom":
                _forward_subgraph_custom_event(writer, capability.graph_id, chunk_data)
                continue
            if chunk_type != "updates":
                continue
            for node_id, node_state in chunk_data.items():
                if not isinstance(node_id, str) or not isinstance(node_state, dict):
                    continue
                final_child_state.update(node_state)
                candidate = node_state.get("workflow_result")
                if isinstance(candidate, dict):
                    workflow_result = candidate
                _emit_subgraph_node_complete(
                    writer,
                    capability.graph_id,
                    node_id,
                    node_state,
                )

        if workflow_result is None:
            raise RuntimeError(
                f"Capability {capability_id} completed without workflow_result"
            )
        evidence = dict(workflow_result.get("evidence") or {})
        retrieved_docs = list(evidence.get("citations") or [])
        log_node_info(
            workflow_id="agent",
            node_id="invoke",
            node_name="调用能力",
            details={
                "能力ID": capability_id,
                "结果状态": workflow_result.get("status"),
                "回答状态": workflow_result.get("answer_status"),
                "引用数": len(retrieved_docs),
            },
        )
        return {
            **_knowledge_diagnostics(final_child_state),
            "handoff_message": handoff_message,
            "workflow_result": workflow_result,
            "answer_status": workflow_result.get("answer_status")
            or final_child_state.get("answer_status"),
            "retrieved_docs": retrieved_docs,
            "backend_citations": retrieved_docs,
        }

    async def _respond_node(state: AgentState) -> dict[str, Any]:
        decision = dict(state.get("decision") or {})
        action = str(decision.get("action") or "").strip()
        answer = str(state.get("answer") or "")
        answer_status = str(state.get("answer_status") or "")
        retrieved_docs = list(state.get("retrieved_docs") or [])
        writer = get_optional_stream_writer()

        if action == "unsupported":
            answer, answer_status = _unsupported_answer()
            retrieved_docs = []
        elif action in {"invoke", "respond"}:
            parts: list[str] = []
            llm = _get_answer_llm(state, answer_factory)
            async for chunk in llm.astream(_build_final_response_prompt(state)):
                text = _coerce_text(getattr(chunk, "content", None))
                if not text:
                    continue
                parts.append(text)
                if writer is not None:
                    writer(
                        {
                            "workflow_id": "agent",
                            "node_id": "respond",
                            "text": text,
                        }
                    )
            answer = "".join(parts).strip()
            if not answer:
                answer = "抱歉，当前没有生成有效回答。"
                answer_status = "generation_failed"
            elif action == "invoke":
                workflow_result = dict(state.get("workflow_result") or {})
                answer_status = str(
                    workflow_result.get("answer_status")
                    or answer_status
                    or "answered"
                )
            else:
                answer_status = "answered"
        if answer and action not in {"invoke", "respond"} and writer is not None:
            writer(
                {
                    "workflow_id": "agent",
                    "node_id": "respond",
                    "text": answer,
                }
            )

        handoff_message = str(state.get("handoff_message") or "").strip()
        if (
            handoff_message
            and answer
            and not _answer_starts_with_handoff(answer, handoff_message)
        ):
            answer = f"{handoff_message}\n\n{answer.lstrip()}"

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
                "处理动作": action,
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

    def _route_after_decide(state: AgentState) -> str:
        action = str((state.get("decision") or {}).get("action") or "").strip()
        if action == "clarify":
            return "clarify"
        if action == "invoke":
            return "invoke"
        if action in {"respond", "unsupported"}:
            return "respond"
        raise ValueError(f"Unsupported decision action: {action or '(empty)'}")

    workflow.add_node("decide", _decide_node)
    workflow.add_node("clarify", _clarify_node)
    workflow.add_node("invoke", _invoke_node)
    workflow.add_node("respond", _respond_node)
    workflow.set_entry_point("decide")
    workflow.add_conditional_edges(
        "decide",
        _route_after_decide,
        {"clarify": "clarify", "invoke": "invoke", "respond": "respond"},
    )
    workflow.add_edge("clarify", "respond")
    workflow.add_edge("invoke", "respond")
    workflow.add_edge("respond", END)
    return workflow.compile()
