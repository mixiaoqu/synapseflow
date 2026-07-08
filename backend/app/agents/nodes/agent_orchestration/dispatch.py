"""Dispatch node for top-level agent orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import get_optional_stream_writer
from app.agents.common.sub_agent_result import build_failed_sub_agent_result
from app.agents.nodes.agent_orchestration.utils import (
    emit_subgraph_node_complete,
    forward_subgraph_custom_event,
    knowledge_diagnostics,
    parse_stream_chunk,
)
from app.agents.runtime.sub_agents import get_sub_agent_definition
from app.agents.states import AgentState


def build_dispatch_node(*, sub_agent_graphs: dict[str, Any]):
    async def dispatch_node(state: AgentState) -> dict[str, Any]:
        writer = get_optional_stream_writer()
        task_plan = dict(state.get("task_plan") or {})
        steps = [dict(step) for step in list(task_plan.get("steps") or [])]

        async def execute_step(step: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            step = dict(step)
            sub_agent_id = str(step.get("sub_agent_id") or "").strip()
            try:
                sub_agent = get_sub_agent_definition(sub_agent_id)
                subgraph = sub_agent_graphs.get(sub_agent_id)
                if subgraph is None:
                    raise RuntimeError(f"Sub-agent graph is not initialized: {sub_agent_id}")
                child_input = sub_agent.input_builder(state, step)
                sub_agent_result: dict[str, Any] | None = None
                final_child_state: dict[str, Any] = {}
                async for chunk in subgraph.astream(
                    child_input,
                    stream_mode=["updates", "custom"],
                    version="v2",
                ):
                    chunk_type, chunk_data = parse_stream_chunk(chunk)
                    if chunk_type == "custom":
                        forward_subgraph_custom_event(
                            writer,
                            sub_agent.graph_id,
                            chunk_data,
                        )
                        continue
                    if chunk_type != "updates":
                        continue
                    for node_id, node_state in chunk_data.items():
                        if not isinstance(node_id, str) or not isinstance(node_state, dict):
                            continue
                        final_child_state.update(node_state)
                        candidate = node_state.get("sub_agent_result")
                        if isinstance(candidate, dict):
                            sub_agent_result = candidate
                        emit_subgraph_node_complete(
                            writer,
                            sub_agent.graph_id,
                            node_id,
                            node_state,
                        )
                if sub_agent_result is None:
                    raise RuntimeError(
                        f"Sub-agent {sub_agent_id} completed without sub_agent_result"
                    )
                return (
                    {
                        "step_id": step.get("step_id"),
                        "sub_agent_id": sub_agent_id,
                        "status": sub_agent_result.get("status") or "failed",
                        "sub_agent_result": sub_agent_result,
                        "node_state": final_child_state,
                    },
                    knowledge_diagnostics(final_child_state),
                )
            except Exception as exc:
                sub_agent_result = build_failed_sub_agent_result(
                    sub_agent_id=sub_agent_id,
                    run_id=state.get("run_id"),
                    step_id=step.get("step_id"),
                    message=str(exc),
                )
                return (
                    {
                        "step_id": step.get("step_id"),
                        "sub_agent_id": sub_agent_id,
                        "status": "failed",
                        "sub_agent_result": sub_agent_result,
                        "node_state": {},
                        "error": str(exc),
                    },
                    {},
                )

        execution_mode = str(task_plan.get("execution_mode") or "sequential")
        if execution_mode == "parallel":
            step_outputs = await asyncio.gather(*(execute_step(step) for step in steps))
        else:
            step_outputs = []
            for step in steps:
                step_outputs.append(await execute_step(step))

        execution_runs: list[dict[str, Any]] = []
        diagnostics: dict[str, Any] = {}
        for execution_run, step_diagnostics in step_outputs:
            execution_runs.append(execution_run)
            diagnostics.update(step_diagnostics)
        log_node_info(
            workflow_id="agent",
            node_id="dispatch",
            node_name="分发执行",
            details={
                "执行模式": execution_mode,
                "执行步骤数": len(execution_runs),
                "成功数": len([run for run in execution_runs if run.get("status") == "success"]),
                "失败数": len([run for run in execution_runs if run.get("status") != "success"]),
            },
        )
        return {**diagnostics, "execution_runs": execution_runs}

    return dispatch_node
