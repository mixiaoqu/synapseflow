"""Subgraph for knowledge-base question answering."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.knowledge_qa.nodes import (
    build_knowledge_qa_retrieval_plan,
    knowledge_qa_retrieve_node,
)
from app.agents.knowledge_qa.query_plan import build_knowledge_query_plan
from app.agents.knowledge_qa.result import build_knowledge_sub_agent_result
from app.agents.knowledge_qa.state import KnowledgeQaState


def create_knowledge_qa_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the reusable knowledge-base QA subgraph."""

    planner_factory = planner_llm_factory or llm_factory
    workflow = StateGraph(KnowledgeQaState)

    async def _plan_query_node(state: KnowledgeQaState) -> dict[str, Any]:
        started_at = perf_counter()
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="plan_query",
            stage="plan",
            message="正在规划知识库检索线索",
            display_stage="understand",
            display_title="🤔 思考您的问题",
            activity_text="分析问题并生成检索线索",
        )
        intent = dict(state.get("intent") or {})
        goal = str(intent.get("goal") or state.get("query") or "").strip()
        query_plan = await build_knowledge_query_plan(
            goal,
            chat_history=list(state.get("chat_history") or []),
            memory_summary=state.get("memory_summary"),
            page_context=dict(state.get("page_context") or {}),
            llm_factory=planner_factory,
        )
        result = dict(query_plan)
        log_node_info(
            workflow_id="knowledge_qa",
            node_id="plan_query",
            node_name="规划查询",
            details={
                "问题类型": query_plan.get("question_type"),
                "检索复杂度": query_plan.get("retrieval_complexity"),
                "语义查询数": len(query_plan.get("semantic_queries") or []),
                "候选实体数": len(query_plan.get("candidate_entities") or []),
                "是否使用HyDE": (query_plan.get("query_plan_trace") or {}).get("hyde_used"),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="plan_query",
            stage="plan",
            message="知识库检索线索规划完成",
            display_stage="understand",
            display_title="🤔 思考您的问题",
            activity_text="已生成查询、关键词和实体线索",
            activity_status="completed",
        )
        return result

    async def _plan_retrieval_node(state: KnowledgeQaState) -> dict[str, Any]:
        started_at = perf_counter()
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="plan_retrieval",
            stage="plan",
            message="正在规划知识库检索",
            display_stage="execute",
            display_title="🔍 查阅相关资料",
            activity_text="确定资料查找范围",
        )
        question_type = str(state.get("question_type") or "definition_lookup")
        retrieval_complexity = str(state.get("retrieval_complexity") or "standard")
        execution_plan = build_knowledge_qa_retrieval_plan(
            question_type=question_type,
            retrieval_strategy="auto",
            retrieval_complexity=retrieval_complexity,
        )
        channels = execution_plan.get("channels") or {}
        graph = channels.get("graph") or {}
        vector = channels.get("vector") or {}
        lexical = channels.get("lexical") or {}
        context = execution_plan.get("context") or {}
        result = {
            "retrieval_strategy": execution_plan["mode"],
            "retrieval_execution_plan": execution_plan,
        }
        log_node_info(
            workflow_id="knowledge_qa",
            node_id="plan_retrieval",
            node_name="规划检索",
            details={
                "检索策略": result.get("retrieval_strategy"),
                "是否启用图谱": graph.get("enabled"),
                "图谱模式": graph.get("graph_mode"),
                "向量TopK": vector.get("recall_k"),
                "关键词TopK": lexical.get("lexical_k"),
                "图谱TopK": graph.get("limit"),
                "上下文TopK": context.get("final_top_k"),
                "重排TopK": ((execution_plan.get("rerank") or {}).get("top_k")),
                "上下文预算": context.get("budget_chars"),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="plan_retrieval",
            stage="plan",
            message="已规划知识库检索",
            display_stage="execute",
            display_title="🔍 查阅相关资料",
            activity_text="已确定资料查找范围",
            activity_status="completed",
        )
        return result

    async def _retrieve_knowledge_node(state: KnowledgeQaState) -> dict[str, Any]:
        started_at = perf_counter()
        result = await knowledge_qa_retrieve_node(state, node_id="retrieve_knowledge")
        retrieval_result = dict(result.get("retrieval_result") or {})
        metrics = dict(retrieval_result.get("metrics") or {})
        log_node_info(
            workflow_id="knowledge_qa",
            node_id="retrieve_knowledge",
            node_name="检索知识",
            details={
                "规划引擎": (state.get("query_plan_trace") or {}).get("engine"),
                "语义查询数": len(state.get("semantic_queries") or []),
                "关键词数": len(state.get("lexical_terms") or []),
                "候选实体数": len(state.get("candidate_entities") or []),
                "关系查询数": len(state.get("relation_queries") or []),
                "检索策略": state.get("retrieval_strategy"),
                "文本命中数": metrics.get("text_hit_count"),
                "图谱命中数": metrics.get("graph_hit_count"),
                "最终主证据数": metrics.get("primary_count"),
                "辅助证据数": metrics.get("supporting_count"),
                "空结果原因": retrieval_result.get("reason_code"),
                "上下文长度": (retrieval_result.get("budget") or {}).get("used_chars"),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        evidence_items = list(retrieval_result.get("evidence_items") or [])
        primary_items = [item for item in evidence_items if item.get("role") == "primary"]
        top_title = ""
        if primary_items:
            source = dict(primary_items[0].get("source") or {})
            top_title = str(source.get("document_title") or "").strip()
        activity_text = (
            f"已找到 {len(primary_items)} 条相关资料"
            if not top_title
            else f"已找到 {len(primary_items)} 条相关资料，包括《{top_title}》"
        )
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="retrieve_knowledge",
            stage="retrieve",
            message="知识库资料查找完成",
            display_stage="execute",
            display_title="🔍 查阅相关资料",
            activity_text=activity_text,
            activity_status="completed",
            retrieved_count=len(primary_items),
        )
        return result

    async def _compose_result_node(state: KnowledgeQaState) -> dict[str, Any]:
        started_at = perf_counter()
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="compose_result",
            stage="compose",
            message="正在整理知识库结果",
            display_stage="compose",
            display_title="💡 总结最终结果",
            activity_text="整理可用于回答的知识库资料",
        )
        sub_agent_result = build_knowledge_sub_agent_result(state)
        retrieval_result = dict(state.get("retrieval_result") or {})
        metrics = dict(retrieval_result.get("metrics") or {})
        log_node_info(
            workflow_id="knowledge_qa",
            node_id="compose_result",
            node_name="整理结果",
            details={
                "结果状态": sub_agent_result.get("status"),
                "主证据数": metrics.get("primary_count"),
                "上下文长度": (retrieval_result.get("budget") or {}).get("used_chars"),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="compose_result",
            stage="compose",
            message="知识库结果整理完成",
            display_stage="compose",
            display_title="💡 总结最终结果",
            activity_text="已整理好知识库资料",
            activity_status="completed",
        )
        return {
            "sub_agent_result": sub_agent_result,
            "answer_status": sub_agent_result.get("answer_status"),
        }

    workflow.add_node("plan_query", _plan_query_node)
    workflow.add_node("plan_retrieval", _plan_retrieval_node)
    workflow.add_node("retrieve_knowledge", _retrieve_knowledge_node)
    workflow.add_node("compose_result", _compose_result_node)
    workflow.set_entry_point("plan_query")
    workflow.add_edge("plan_query", "plan_retrieval")
    workflow.add_edge("plan_retrieval", "retrieve_knowledge")
    workflow.add_edge("retrieve_knowledge", "compose_result")
    workflow.add_edge("compose_result", END)
    return workflow.compile()
