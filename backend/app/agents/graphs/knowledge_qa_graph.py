"""Subgraph for knowledge-base question answering."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.common.knowledge_question_analysis import build_knowledge_question_analysis
from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.nodes.kb_chat import (
    build_kb_chat_answer_node,
    kb_chat_retrieve_node,
    kb_chat_rewrite_query_node,
)
from app.agents.nodes.knowledge_qa import build_knowledge_qa_retrieval_plan
from app.agents.states import KnowledgeQaState


def create_knowledge_qa_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the reusable knowledge-base QA subgraph."""

    planner_factory = planner_llm_factory or llm_factory
    answer_factory = answer_llm_factory or llm_factory
    workflow = StateGraph(KnowledgeQaState)
    compose_node = build_kb_chat_answer_node(
        llm_factory=answer_factory,
        node_id="compose_answer",
    )

    async def _analyze_question_node(state: KnowledgeQaState) -> dict[str, Any]:
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="analyze_question",
            stage="analyze",
            message="正在分析知识库问题",
            display_stage="understand",
            display_title="🤔 思考您的问题",
            activity_text="正在判断问题重点",
        )
        page_context = dict(state.get("page_context") or {})
        page_config = dict(state.get("page_config") or {})
        analysis = await build_knowledge_question_analysis(
            str(state.get("query") or ""),
            chat_history=list(state.get("chat_history") or []),
            memory_summary=state.get("memory_summary"),
            page_type=page_context.get("page_type") or page_config.get("page_type"),
            llm_factory=planner_factory,
        )
        result = {
            "question_type": analysis["question_type"],
            "retrieval_complexity": analysis["retrieval_complexity"],
            "retrieval_required": True,
            "candidate_entities": list(analysis.get("entities") or []),
            "question_intent": {
                "question_type": analysis["question_type"],
                "entities": list(analysis.get("entities") or []),
                "needs_path": bool(analysis.get("needs_path")),
                "needs_relation": bool(analysis.get("needs_relation")),
                "needs_summary": bool(analysis.get("needs_summary")),
            },
            "route_reason": analysis.get("reason") or "",
            "question_analysis": analysis,
        }
        log_node_info(
            workflow_id="knowledge_qa",
            node_id="analyze_question",
            node_name="分析问题",
            details={
                "问题类型": result.get("question_type"),
                "问题复杂度": result.get("retrieval_complexity"),
                "候选实体数": len(result.get("candidate_entities") or []),
                "判断原因": result.get("route_reason"),
            },
        )
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="analyze_question",
            stage="analyze",
            message="已分析知识库问题",
            display_stage="understand",
            display_title="🤔 思考您的问题",
            activity_text="已明确需要查找的资料方向",
            activity_status="completed",
        )
        return result

    async def _plan_retrieval_node(state: KnowledgeQaState) -> dict[str, Any]:
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="plan_retrieval",
            stage="plan",
            message="正在规划知识库检索",
            display_stage="execute",
            display_title="🔍 查阅相关资料",
            activity_text="正在确定资料查找范围",
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
        rewrite = await kb_chat_rewrite_query_node(
            state,
            node_id="retrieve_knowledge",
        )
        prepared_state = {**state, **rewrite}
        result = await kb_chat_retrieve_node(prepared_state, node_id="retrieve_knowledge")
        result = {
            **rewrite,
            **result,
            "retrieval": {
                "question_type": state.get("question_type"),
                "strategy": state.get("retrieval_strategy"),
                "complexity": state.get("retrieval_complexity"),
                "plan": state.get("retrieval_execution_plan") or {},
                "queries": {
                    "semantic": list(rewrite.get("semantic_queries") or []),
                    "lexical": list(rewrite.get("lexical_terms") or []),
                    "entities": list(rewrite.get("candidate_entities") or []),
                    "relations": list(rewrite.get("relation_queries") or []),
                },
            },
        }
        retrieval_trace = dict(result.get("retrieval_trace") or {})
        text_trace = dict(retrieval_trace.get("text") or {})
        graph_trace = dict(retrieval_trace.get("graph") or {})
        rewrite_trace = dict(result.get("rewrite_trace") or {})
        result["evidence"] = {
            "docs": list(result.get("retrieved_docs") or []),
            "context": {
                "primary": result.get("primary_context") or "",
                "supporting": result.get("supporting_context") or "",
            },
            "stats": {
                "text_hits": text_trace.get("text_hits"),
                "graph_hits": graph_trace.get("graph_hits"),
                "final_count": len(result.get("retrieved_docs") or []),
            },
            "status": "found" if result.get("retrieved_docs") else "empty",
        }
        log_node_info(
            workflow_id="knowledge_qa",
            node_id="retrieve_knowledge",
            node_name="检索知识",
            details={
                "改写引擎": rewrite_trace.get("engine"),
                "语义查询数": len(result.get("semantic_queries") or []),
                "关键词数": len(result.get("lexical_terms") or []),
                "候选实体数": len(result.get("candidate_entities") or []),
                "关系查询数": len(result.get("relation_queries") or []),
                "检索策略": retrieval_trace.get("retrieval_strategy"),
                "文本命中数": text_trace.get("text_hits"),
                "图谱命中数": graph_trace.get("graph_hits"),
                "最终主证据数": len(result.get("retrieved_docs") or []),
                "辅助证据数": len(result.get("supporting_evidence_docs") or []),
                "空结果原因": retrieval_trace.get("empty_reason"),
                "上下文长度": len(result.get("context") or ""),
            },
        )
        retrieved_docs = list(result.get("retrieved_docs") or [])
        top_title = ""
        if retrieved_docs:
            metadata = dict(retrieved_docs[0].get("metadata") or {})
            top_title = str(metadata.get("document_title") or "").strip()
        activity_text = (
            f"已找到 {len(retrieved_docs)} 条相关资料"
            if not top_title
            else f"已找到 {len(retrieved_docs)} 条相关资料，包括《{top_title}》"
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
            retrieved_count=len(retrieved_docs),
        )
        return result

    async def _compose_answer_node(state: KnowledgeQaState) -> dict[str, Any]:
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="compose_answer",
            stage="compose",
            message="正在整理知识库回复",
            display_stage="compose",
            display_title="💡 总结最终结果",
            activity_text="正在把查到的资料整理成回复",
        )
        result = await compose_node(state)
        answer_trace = dict(result.get("answer_trace") or {})
        knowledge_answer = {
            "text": result.get("answer") or "",
            "status": result.get("answer_status"),
            "citations": list(state.get("retrieved_docs") or []),
            "metadata": {
                "retrieved_count": len(state.get("retrieved_docs") or []),
                "context_length": len(state.get("context") or ""),
            },
        }
        result["knowledge_answer"] = knowledge_answer
        log_node_info(
            workflow_id="knowledge_qa",
            node_id="compose_answer",
            node_name="组织回答",
            details={
                "回答状态": result.get("answer_status"),
                "回答长度": len(result.get("answer") or ""),
                "输出Token估算": answer_trace.get("output_tokens"),
                "首Token耗时毫秒": answer_trace.get("first_token_latency_ms"),
                "总耗时毫秒": answer_trace.get("latency_ms"),
            },
        )
        emit_activity(
            get_optional_stream_writer(),
            workflow_id="knowledge_qa",
            node_id="compose_answer",
            stage="compose",
            message="知识库回复整理完成",
            display_stage="compose",
            display_title="💡 总结最终结果",
            activity_text="已整理好知识库回复",
            activity_status="completed",
        )
        return result

    workflow.add_node("analyze_question", _analyze_question_node)
    workflow.add_node("plan_retrieval", _plan_retrieval_node)
    workflow.add_node("retrieve_knowledge", _retrieve_knowledge_node)
    workflow.add_node("compose_answer", _compose_answer_node)
    workflow.set_entry_point("analyze_question")
    workflow.add_edge("analyze_question", "plan_retrieval")
    workflow.add_edge("plan_retrieval", "retrieve_knowledge")
    workflow.add_edge("retrieve_knowledge", "compose_answer")
    workflow.add_edge("compose_answer", END)
    return workflow.compile()
