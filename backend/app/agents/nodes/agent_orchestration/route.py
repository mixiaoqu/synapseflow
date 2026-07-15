"""Route node for top-level agent orchestration."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.nodes.agent_orchestration.constants import (
    ROUTE_APPROVAL,
    ROUTE_CLARIFY_MAIN,
    ROUTE_DIRECT_RESPONSE,
    ROUTE_MULTI_SUB_AGENT,
    ROUTE_SAFE_BLOCK,
    ROUTE_SINGLE_SUB_AGENT,
    ROUTE_UNSUPPORTED,
)
from app.agents.states import AgentState


def build_route(
    classification: dict[str, Any],
    *,
    available_sub_agent_ids: set[str],
) -> dict[str, Any]:
    risk_hint = str(classification.get("risk_hint") or "none").strip()
    task_shape = str(classification.get("task_shape") or "non_executable").strip()
    goal_clarity = str(classification.get("goal_clarity") or "unclear").strip()
    needs_sub_agent = bool(classification.get("needs_sub_agent"))
    domain_hints = [
        item
        for item in list(classification.get("domain_hints") or [])
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
    elif task_shape == "multi_sub_agent" and len(domain_hints) > 1:
        route_type = ROUTE_MULTI_SUB_AGENT
    elif task_shape in {"single_sub_agent", "multi_sub_agent"} and domain_hints:
        route_type = ROUTE_SINGLE_SUB_AGENT
    elif needs_sub_agent:
        route_type = ROUTE_UNSUPPORTED
    elif task_shape == "non_executable":
        route_type = ROUTE_UNSUPPORTED
    else:
        route_type = ROUTE_DIRECT_RESPONSE

    return {
        "route_type": route_type,
        "target_sub_agents": domain_hints,
        "reason": classification.get("reason") or "已完成主路径分流。",
    }


def build_route_node(*, available_sub_agent_ids: set[str]):
    async def route_node(state: AgentState) -> dict[str, Any]:
        started_at = perf_counter()
        writer = get_optional_stream_writer()
        classification = dict(state.get("classification") or {})
        emit_activity(
            writer,
            workflow_id="agent",
            node_id="route",
            stage="route",
            message="正在选择处理路径",
            display_stage="route",
            display_title="选择路径",
            activity_text="选择主处理分支",
        )
        route = build_route(
            classification,
            available_sub_agent_ids=available_sub_agent_ids,
        )
        log_node_info(
            workflow_id="agent",
            node_id="route",
            node_name="选择路径",
            details={
                "路由类型": route.get("route_type"),
                "目标子智能体": route.get("target_sub_agents"),
                "路由原因": route.get("reason"),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        emit_activity(
            writer,
            workflow_id="agent",
            node_id="route",
            stage="route",
            message="处理路径选择完成",
            display_stage="route",
            display_title="选择路径",
            activity_text="已确定主处理分支",
            activity_status="completed",
        )
        return {"route": route}

    return route_node
