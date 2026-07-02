"""Top-level agent workflow graph."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.common.agent_intent import build_agent_intent
from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import get_optional_stream_writer
from app.agents.graphs.business_ops_graph import create_business_ops_graph
from app.agents.graphs.knowledge_qa_graph import create_knowledge_qa_graph
from app.agents.nodes.kb_chat.answer import KB_CHITCHAT_REPLY, KB_OUT_OF_SCOPE_REPLY
from app.agents.states import AgentState


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


def _forward_subgraph_custom_event(
    writer: Callable[[dict[str, Any]], None] | None,
    workflow_id: str,
    data: dict[str, Any],
) -> None:
    if writer is None:
        return

    payload = dict(data)
    payload.setdefault("workflow_id", workflow_id)
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


def _direct_answer_for_intent(intent: dict[str, Any]) -> tuple[str, str]:
    direct_answer_kind = str(intent.get("direct_answer_kind") or "").strip()
    if direct_answer_kind == "chitchat":
        return KB_CHITCHAT_REPLY, "chitchat"
    if direct_answer_kind == "out_of_scope":
        return KB_OUT_OF_SCOPE_REPLY, "out_of_scope"
    return KB_OUT_OF_SCOPE_REPLY, "out_of_scope"


def create_agent_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the top-level agent workflow graph."""

    planner_factory = planner_llm_factory or llm_factory
    knowledge_qa_graph = create_knowledge_qa_graph(
        planner_llm_factory=planner_factory,
        answer_llm_factory=answer_llm_factory or llm_factory,
    )
    business_ops_graph = create_business_ops_graph()
    workflow = StateGraph(AgentState)

    async def _load_context_node(state: AgentState) -> dict[str, Any]:
        metadata = dict(state.get("metadata") or {})
        metadata["workflow"] = "agent"
        runtime_context = {
            "assistant": {
                "id": state.get("assistant_id"),
                "name": state.get("assistant_name"),
                "llm_model_key": state.get("assistant_llm_model_key"),
            },
            "scope": {
                "team_id": state.get("team_id"),
                "knowledge_base_id": state.get("knowledge_base_id"),
                "category_id": state.get("category_id"),
                "allowed_document_statuses": list(state.get("allowed_document_statuses") or []),
            },
            "page": {
                "context": dict(state.get("page_context") or {}),
                "config": dict(state.get("page_config") or {}),
            },
            "business": {
                "store_id": state.get("store_id"),
            },
            "memory": {
                "chat_history": list(state.get("chat_history") or []),
                "memory_summary": state.get("memory_summary"),
            },
        }
        result = {
            "workflow_id": "agent",
            "metadata": metadata,
            "runtime_context": runtime_context,
        }
        log_node_info(
            workflow_id="agent",
            node_id="load_context",
            node_name="加载上下文",
            details={
                "运行ID": state.get("run_id"),
                "会话ID": state.get("session_id"),
                "用户ID": state.get("user_id"),
                "团队ID": state.get("team_id"),
                "知识库ID": state.get("knowledge_base_id"),
                "分类ID": state.get("category_id"),
                "历史消息数": len(state.get("chat_history") or []),
            },
        )
        return result

    async def _understand_node(state: AgentState) -> dict[str, Any]:
        query = str(state.get("query") or "").strip()
        if not query:
            intent = {
                "type": "clarify",
                "needs_clarification": True,
                "missing_fields": ["query"],
                "reason": "用户问题为空，需要补齐问题内容。",
            }
        else:
            page_context = dict(state.get("page_context") or {})
            page_config = dict(state.get("page_config") or {})
            intent_result = await build_agent_intent(
                query,
                chat_history=list(state.get("chat_history") or []),
                memory_summary=state.get("memory_summary"),
                page_type=page_context.get("page_type") or page_config.get("page_type"),
                llm_factory=planner_factory,
            )
            intent_type = str(intent_result.get("type") or "direct_answer").strip()
            intent = {
                "type": intent_type,
                "needs_clarification": bool(intent_result.get("needs_clarification")),
                "missing_fields": list(intent_result.get("missing_fields") or []),
                "direct_answer_kind": intent_result.get("direct_answer_kind"),
                "reason": intent_result.get("reason"),
            }
        log_node_info(
            workflow_id="agent",
            node_id="understand",
            node_name="理解意图",
            details={
                "意图类型": intent.get("type"),
                "是否需要澄清": intent.get("needs_clarification"),
                "缺失字段": intent.get("missing_fields"),
                "直接回复类型": intent.get("direct_answer_kind"),
                "判断原因": intent.get("reason"),
            },
        )
        return {"intent": intent}

    async def _route_node(state: AgentState) -> dict[str, Any]:
        intent = dict(state.get("intent") or {})
        intent_type = str(intent.get("type") or "").strip()
        route_targets = {
            "clarify": ("clarify", "clarify"),
            "knowledge_qa": ("workflow", "knowledge_qa"),
            "business_ops": ("workflow", "business_ops"),
            "direct_answer": ("direct", "direct_answer"),
        }
        target_type, target_id = route_targets.get(intent_type, ("direct", "direct_answer"))
        result = {
            "target_type": target_type,
            "target_id": target_id,
            "reason": intent.get("reason"),
        }
        log_node_info(
            workflow_id="agent",
            node_id="route",
            node_name="匹配能力",
            details={
                "目标类型": result["target_type"],
                "目标ID": result["target_id"],
                "原因": result.get("reason"),
            },
        )
        return {"route": result}

    async def _clarify_node(state: AgentState) -> dict[str, Any]:
        intent = dict(state.get("intent") or {})
        missing_fields = list(intent.get("missing_fields") or [])
        question = "请补充你想咨询的具体问题。"
        if missing_fields and missing_fields != ["query"]:
            question = "为了继续处理，请补充必要的信息。"
        clarification = {
            "question": question,
            "missing_fields": missing_fields,
        }
        log_node_info(
            workflow_id="agent",
            node_id="clarify",
            node_name="请求澄清",
            details={
                "澄清问题": question,
                "缺失字段": missing_fields,
            },
        )
        return {
            "clarification": clarification,
            "answer": question,
            "answer_status": "clarification_needed",
            "retrieved_docs": [],
        }

    async def _plan_node(state: AgentState) -> dict[str, Any]:
        route = dict(state.get("route") or {})
        target_type = str(route.get("target_type") or "").strip()
        target_id = str(route.get("target_id") or "").strip()
        steps: list[dict[str, Any]] = []
        if target_type == "workflow" and target_id == "knowledge_qa":
            steps.append(
                {
                    "id": "step_1",
                    "type": "workflow",
                    "target_id": "knowledge_qa",
                    "input": "current_context",
                }
            )
        if target_type == "workflow" and target_id == "business_ops":
            steps.append(
                {
                    "id": "step_1",
                    "type": "workflow",
                    "target_id": "business_ops",
                    "input": "current_context",
                }
            )
        result = {"steps": steps}
        log_node_info(
            workflow_id="agent",
            node_id="plan",
            node_name="制定计划",
            details={
                "步骤数": len(steps),
                "目标类型": target_type,
                "目标ID": target_id,
            },
        )
        return {"plan": result}

    async def _execute_node(state: AgentState) -> dict[str, Any]:
        plan = dict(state.get("plan") or {})
        steps = list(plan.get("steps") or [])
        step_results: list[dict[str, Any]] = []
        final_result: dict[str, Any] = {}
        stream_writer = get_optional_stream_writer()
        for step in steps:
            if step.get("type") != "workflow":
                continue
            target_id = str(step.get("target_id") or "").strip()
            if target_id == "knowledge_qa":
                subgraph = knowledge_qa_graph
            elif target_id == "business_ops":
                subgraph = business_ops_graph
            else:
                continue

            async for chunk in subgraph.astream(
                state,
                stream_mode=["updates", "custom"],
                version="v2",
            ):
                chunk_type, chunk_data = _parse_stream_chunk(chunk)
                if chunk_type == "custom":
                    _forward_subgraph_custom_event(stream_writer, target_id, chunk_data)
                    continue
                if chunk_type != "updates":
                    continue

                for node_id, node_state in chunk_data.items():
                    if not isinstance(node_id, str) or not isinstance(node_state, dict):
                        continue
                    final_result.update(node_state)
                    _emit_subgraph_node_complete(stream_writer, target_id, node_id, node_state)

            step_results.append(
                {
                    "step_id": step.get("id"),
                    "type": "workflow",
                    "target_id": target_id,
                    "status": "success",
                    "answer_status": final_result.get("answer_status"),
                    "retrieved_count": len(final_result.get("retrieved_docs") or []),
                }
            )
        execution = {
            "status": "success" if step_results else "skipped",
            "results": step_results,
        }
        log_node_info(
            workflow_id="agent",
            node_id="execute",
            node_name="执行计划",
            details={
                "执行状态": execution["status"],
                "执行步骤数": len(step_results),
                "检索文档数": len(final_result.get("retrieved_docs") or []),
                "回答状态": final_result.get("answer_status"),
            },
        )
        return {
            **final_result,
            "execution": execution,
        }

    async def _respond_node(state: AgentState) -> dict[str, Any]:
        route = dict(state.get("route") or {})
        target_type = str(route.get("target_type") or "").strip()
        target_id = str(route.get("target_id") or "").strip()
        answer = str(state.get("answer") or "")
        answer_status = str(state.get("answer_status") or "")
        retrieved_docs = list(state.get("retrieved_docs") or [])
        if target_type == "direct" and target_id == "direct_answer":
            answer, answer_status = _direct_answer_for_intent(dict(state.get("intent") or {}))
            retrieved_docs = []
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
                "回答状态": response["answer_status"],
                "回答长度": len(response["answer"]),
                "引用数": len(response["citations"]),
                "目标类型": target_type,
                "目标ID": target_id,
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

    def _route_after_route(state: AgentState) -> str:
        route = dict(state.get("route") or {})
        target_type = str(route.get("target_type") or "").strip()
        target_id = str(route.get("target_id") or "").strip()
        if target_type == "clarify" and target_id == "clarify":
            return "clarify"
        if target_type == "workflow" and target_id == "knowledge_qa":
            return "plan"
        if target_type == "workflow" and target_id == "business_ops":
            return "plan"
        return "respond"

    workflow.add_node("load_context", _load_context_node)
    workflow.add_node("understand", _understand_node)
    workflow.add_node("route", _route_node)
    workflow.add_node("clarify", _clarify_node)
    workflow.add_node("plan", _plan_node)
    workflow.add_node("execute", _execute_node)
    workflow.add_node("respond", _respond_node)
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "understand")
    workflow.add_edge("understand", "route")
    workflow.add_conditional_edges(
        "route",
        _route_after_route,
        {"clarify": "clarify", "plan": "plan", "respond": "respond"},
    )
    workflow.add_edge("clarify", "respond")
    workflow.add_edge("plan", "execute")
    workflow.add_edge("execute", "respond")
    workflow.add_edge("respond", END)
    return workflow.compile()
