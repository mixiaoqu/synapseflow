"""Semantic understanding plus deterministic routing."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.main.intent import build_agent_classification
from app.agents.main.nodes.constants import (
    ROUTE_APPROVAL,
    ROUTE_CLARIFY_MAIN,
    ROUTE_DIRECT_RESPONSE,
    ROUTE_MULTI_SUB_AGENT,
    ROUTE_SAFE_BLOCK,
    ROUTE_SINGLE_SUB_AGENT,
    ROUTE_UNSUPPORTED,
)
from app.agents.main.state import AgentState
from app.agents.runtime.sub_agents import SubAgentDefinition


def decide_route(
    understanding: dict[str, Any],
    *,
    available_sub_agent_ids: set[str],
) -> dict[str, Any]:
    """Apply platform policy in code after the model understands semantics."""

    risk_hint = str(understanding.get("risk_hint") or "none")
    task_shape = str(understanding.get("task_shape") or "non_executable")
    goal_clarity = str(understanding.get("goal_clarity") or "unclear")
    targets = [
        str(item)
        for item in list(understanding.get("domain_hints") or [])
        if str(item) in available_sub_agent_ids
    ]
    if risk_hint == "safe_block":
        route_type = ROUTE_SAFE_BLOCK
    elif risk_hint == "approval":
        route_type = ROUTE_APPROVAL
    elif goal_clarity != "clear":
        route_type = ROUTE_CLARIFY_MAIN
    elif task_shape == "direct":
        route_type = ROUTE_DIRECT_RESPONSE
    elif task_shape == "multi_sub_agent" and len(targets) > 1:
        route_type = ROUTE_MULTI_SUB_AGENT
    elif task_shape in {"single_sub_agent", "multi_sub_agent"} and targets:
        route_type = ROUTE_SINGLE_SUB_AGENT
    else:
        route_type = ROUTE_UNSUPPORTED
    return {
        "route_type": route_type,
        "intent": dict(understanding.get("intent") or {}),
        "target_sub_agents": targets,
        "reason": understanding.get("reason") or "已完成路径决策。",
        "risk_hint": risk_hint,
    }


def build_route_node(
    *,
    sub_agents: tuple[SubAgentDefinition, ...],
    planner_llm_factory: Callable[[], Any] | None,
):
    async def route_node(state: AgentState) -> dict[str, Any]:
        started_at = perf_counter()
        writer = get_optional_stream_writer()
        agent_input = state["input"]
        conversation = agent_input["conversation"]
        emit_activity(
            writer,
            workflow_id="agent",
            node_id="route",
            stage="route",
            message="正在理解需求并选择处理路径",
            activity_text="理解需求并选择主处理分支",
        )
        understanding = await build_agent_classification(
            agent_input["query"],
            sub_agents=sub_agents,
            chat_history=list(conversation.get("history") or []),
            memory_summary=conversation.get("summary"),
            page_context=dict(agent_input["page_context"]),
            runtime_context=dict(agent_input["runtime_context"]),
            llm_factory=planner_llm_factory,
        )
        routing = decide_route(
            understanding,
            available_sub_agent_ids={item.sub_agent_id for item in sub_agents},
        )
        log_node_info(
            workflow_id="agent",
            node_id="route",
            node_name="理解与路由",
            details={
                "路由类型": routing["route_type"],
                "目标能力": routing["target_sub_agents"],
                "原因": routing["reason"],
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        return {"routing": routing}

    return route_node
