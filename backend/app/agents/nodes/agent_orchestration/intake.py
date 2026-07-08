"""Intake node for top-level agent orchestration."""

from __future__ import annotations

from typing import Any

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.nodes.agent_orchestration.utils import normalize_query
from app.agents.states import AgentState


async def intake_node(state: AgentState) -> dict[str, Any]:
    writer = get_optional_stream_writer()
    emit_activity(
        writer,
        workflow_id="agent",
        node_id="intake",
        stage="intake",
        message="正在整理请求上下文",
        display_stage="intake",
        display_title="整理上下文",
        activity_text="统一请求、会话和页面上下文",
    )
    normalized_query = normalize_query(state.get("query"))
    scope = {
        "user_id": state.get("user_id"),
        "team_id": state.get("team_id"),
        "knowledge_base_id": state.get("knowledge_base_id"),
        "category_id": state.get("category_id"),
        "product_id": state.get("product_id"),
        "project_id": state.get("project_id"),
        "project_app_id": state.get("project_app_id"),
        "store_id": state.get("store_id"),
    }
    session_context = {
        "session_id": state.get("session_id"),
        "request_id": state.get("request_id"),
        "run_id": state.get("run_id"),
        "chat_history": list(state.get("chat_history") or []),
        "memory_summary": state.get("memory_summary"),
    }
    channel_context = {
        "page_context": dict(state.get("page_context") or {}),
        "page_config": dict(state.get("page_config") or {}),
        "channel": (state.get("metadata") or {}).get("channel"),
        "source_surface": (state.get("metadata") or {}).get("source_surface"),
    }
    trace = {
        **dict(state.get("trace") or {}),
        "workflow_id": "agent",
        "normalized_query_chars": len(normalized_query),
    }
    log_node_info(
        workflow_id="agent",
        node_id="intake",
        node_name="整理上下文",
        details={
            "问题长度": len(normalized_query),
            "会话ID": session_context.get("session_id"),
            "团队ID": scope.get("team_id"),
            "知识库ID": scope.get("knowledge_base_id"),
        },
    )
    emit_activity(
        writer,
        workflow_id="agent",
        node_id="intake",
        stage="intake",
        message="请求上下文整理完成",
        display_stage="intake",
        display_title="整理上下文",
        activity_text="已形成统一输入态",
        activity_status="completed",
    )
    return {
        "normalized_query": normalized_query,
        "query": normalized_query,
        "scope": scope,
        "session_context": session_context,
        "channel_context": channel_context,
        "trace": trace,
    }
