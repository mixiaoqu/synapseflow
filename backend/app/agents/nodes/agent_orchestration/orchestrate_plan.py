"""Task-level planning node for top-level agent orchestration."""

from __future__ import annotations

from typing import Any

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.nodes.agent_orchestration.constants import EXECUTION_ROUTE_TYPES
from app.agents.states import AgentState


def _execution_mode(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return "none"
    if len(steps) == 1:
        return "single"
    if all(not step.get("dependencies") for step in steps):
        return "parallel"
    return "dag"


def build_task_plan(state: dict[str, Any]) -> dict[str, Any]:
    route = dict(state.get("route") or {})
    classification = dict(state.get("classification") or {})
    intent = dict(classification.get("intent") or {})
    target_sub_agents = list(route.get("target_sub_agents") or [])
    route_type = str(route.get("route_type") or "")
    if route_type not in EXECUTION_ROUTE_TYPES or not target_sub_agents:
        return {
            "execution_mode": "none",
            "steps": [],
            "reason": "当前路由无需子智能体执行。",
        }

    steps = []
    sub_tasks = [
        dict(item)
        for item in list(classification.get("sub_tasks") or [])
        if isinstance(item, dict)
        and str(item.get("sub_agent_id") or "").strip() in target_sub_agents
    ]
    if sub_tasks:
        step_id_by_sub_agent = {
            str(item.get("sub_agent_id") or "").strip(): f"step_{index}"
            for index, item in enumerate(sub_tasks, start=1)
        }
        for index, item in enumerate(sub_tasks, start=1):
            sub_agent_id = str(item.get("sub_agent_id") or "").strip()
            dependencies = [
                step_id_by_sub_agent.get(dependency, dependency)
                for dependency in list(item.get("depends_on") or [])
                if isinstance(dependency, str) and dependency.strip()
            ]
            steps.append(
                {
                    "step_id": f"step_{index}",
                    "sub_agent_id": sub_agent_id,
                    "goal": item.get("goal")
                    or intent.get("goal")
                    or state.get("normalized_query")
                    or "",
                    "dependencies": dependencies,
                    "on_failure": "collect_failure",
                }
            )
    else:
        for index, sub_agent_id in enumerate(target_sub_agents, start=1):
            steps.append(
                {
                    "step_id": f"step_{index}",
                    "sub_agent_id": sub_agent_id,
                    "goal": intent.get("goal") or state.get("normalized_query") or "",
                    "dependencies": [],
                    "on_failure": "collect_failure",
                }
            )
    execution_mode = _execution_mode(steps)
    for step in steps:
        step["execution_mode"] = execution_mode
    return {
        "execution_mode": execution_mode,
        "steps": steps,
        "reason": route.get("reason") or "已生成任务级执行计划。",
    }


async def orchestrate_plan_node(state: AgentState) -> dict[str, Any]:
    writer = get_optional_stream_writer()
    emit_activity(
        writer,
        workflow_id="agent",
        node_id="orchestrate_plan",
        stage="plan",
        message="正在生成任务级执行计划",
        display_stage="orchestrate_plan",
        display_title="规划执行",
        activity_text="确定能力步骤和执行顺序",
    )
    task_plan = build_task_plan(state)
    log_node_info(
        workflow_id="agent",
        node_id="orchestrate_plan",
        node_name="规划执行",
        details={
            "执行模式": task_plan.get("execution_mode"),
            "步骤数": len(task_plan.get("steps") or []),
            "规划原因": task_plan.get("reason"),
        },
    )
    emit_activity(
        writer,
        workflow_id="agent",
        node_id="orchestrate_plan",
        stage="plan",
        message="任务级执行计划生成完成",
        display_stage="orchestrate_plan",
        display_title="规划执行",
        activity_text="已生成任务级执行计划",
        activity_status="completed",
    )
    return {"task_plan": task_plan}
