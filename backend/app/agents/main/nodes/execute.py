"""DAG execution node for top-level agent orchestration."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from loguru import logger

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import get_optional_stream_writer
from app.agents.common.task_result import build_failed_task_result
from app.agents.main.nodes.utils import (
    emit_subgraph_node_complete,
    forward_subgraph_custom_event,
    knowledge_diagnostics,
    parse_stream_chunk,
)
from app.agents.main.state import AgentState
from app.agents.runtime.handlers import get_handler_definition


def build_execute_node(*, handler_workflows: dict[str, Any]):
    async def execute_node(state: AgentState) -> dict[str, Any]:
        started_at = perf_counter()
        writer = get_optional_stream_writer()
        task_plan = dict(state.get("execution_plan") or {})
        steps = [dict(step) for step in list(task_plan.get("steps") or [])]

        def dependency_inputs(
            step: dict[str, Any], execution_runs_by_id: dict[str, dict[str, Any]]
        ) -> dict[str, dict[str, Any]]:
            return {
                dependency_id: {
                    "task_id": dependency_id,
                    "handler_id": dependency_run.get("handler_id"),
                    "status": dependency_run.get("status"),
                    "task_result": dict(dependency_run.get("task_result") or {}),
                }
                for dependency_id in list(step.get("depends_on") or [])
                if (dependency_run := execution_runs_by_id.get(dependency_id)) is not None
            }

        def build_blocked_run(
            step: dict[str, Any],
            *,
            dependency_results: dict[str, dict[str, Any]],
            message: str,
            code: str,
        ) -> dict[str, Any]:
            handler_id = str(step.get("handler_id") or "").strip()
            task_result = build_failed_task_result(
                handler_id=handler_id or "unassigned",
                run_id=state["input"]["run_id"],
                step_id=step.get("task_id"),
                message=message,
            )
            task_result["errors"] = [
                {
                    "code": code,
                    "message": message,
                    "retryable": False,
                    "details": {"dependencies": dependency_results},
                }
            ]
            return {
                "task_id": step.get("task_id"),
                "goal": step.get("goal"),
                "handler_id": handler_id or None,
                "status": "blocked",
                "task_result": task_result,
                "dependency_results": dependency_results,
                "diagnostics": {},
                "error": message,
            }

        async def execute_step(
            step: dict[str, Any], dependency_results: dict[str, dict[str, Any]]
        ) -> dict[str, Any]:
            step = dict(step)
            handler_id = str(step.get("handler_id") or "").strip()
            try:
                if not handler_id:
                    return build_blocked_run(
                        step,
                        dependency_results=dependency_results,
                        message="当前没有任务处理器能够承接该任务。",
                        code="HANDLER_UNASSIGNED",
                    )
                handler = get_handler_definition(handler_id)
                subgraph = handler_workflows.get(handler_id)
                if subgraph is None:
                    raise RuntimeError(f"Handler workflow is not initialized: {handler_id}")
                step["dependency_results"] = dependency_results
                child_input = handler.input_builder(state, step)
                task_result: dict[str, Any] | None = None
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
                            handler.workflow_id,
                            chunk_data,
                        )
                        continue
                    if chunk_type != "updates":
                        continue
                    for node_id, node_state in chunk_data.items():
                        if not isinstance(node_id, str) or not isinstance(node_state, dict):
                            continue
                        final_child_state.update(node_state)
                        candidate = node_state.get("task_result")
                        if isinstance(candidate, dict):
                            task_result = candidate
                        emit_subgraph_node_complete(
                            writer,
                            handler.workflow_id,
                            node_id,
                            node_state,
                        )
                if task_result is None:
                    raise RuntimeError(
                        f"Handler {handler_id} completed without task_result"
                    )
                return {
                    "task_id": step.get("task_id"),
                    "goal": step.get("goal"),
                    "handler_id": handler_id,
                    "status": task_result.get("status") or "failed",
                    "task_result": task_result,
                    "dependency_results": dependency_results,
                    "diagnostics": knowledge_diagnostics(final_child_state),
                }
            except Exception as exc:
                logger.exception(
                    "[agent.execute] handler execution failed | "
                    "handler_id={} task_id={} error={}",
                    handler_id,
                    step.get("task_id"),
                    exc,
                )
                task_result = build_failed_task_result(
                    handler_id=handler_id or "unassigned",
                    run_id=state["input"]["run_id"],
                    step_id=step.get("task_id"),
                    message="任务处理器执行失败。",
                )
                return {
                    "task_id": step.get("task_id"),
                    "goal": step.get("goal"),
                    "handler_id": handler_id or None,
                    "status": "failed",
                    "task_result": task_result,
                    "dependency_results": dependency_results,
                    "diagnostics": {},
                    "error": "任务处理器执行失败。",
                }

        execution_runs: dict[str, dict[str, Any]] = {}
        execution_runs_by_id = execution_runs
        remaining_steps = {str(step.get("task_id") or ""): step for step in steps}
        execution_mode = str(task_plan.get("execution_mode") or "dag")

        while remaining_steps:
            invalid_steps = [
                step
                for step in remaining_steps.values()
                if any(
                    dependency_id not in remaining_steps
                    and dependency_id not in execution_runs_by_id
                    for dependency_id in list(step.get("depends_on") or [])
                )
            ]
            blocked_steps = [
                step
                for step in remaining_steps.values()
                if step not in invalid_steps
                and any(
                    execution_runs_by_id.get(dependency_id, {}).get("status") != "success"
                    for dependency_id in list(step.get("depends_on") or [])
                    if dependency_id in execution_runs_by_id
                )
            ]
            for step in [*invalid_steps, *blocked_steps]:
                step_id = str(step.get("task_id") or "")
                dependency_results = dependency_inputs(step, execution_runs_by_id)
                code = "UNKNOWN_DEPENDENCY" if step in invalid_steps else "DEPENDENCY_FAILED"
                message = (
                    "任务计划引用了不存在的依赖步骤。"
                    if code == "UNKNOWN_DEPENDENCY"
                    else "前序步骤未成功完成，当前步骤不会执行。"
                )
                execution_run = build_blocked_run(
                    step,
                    dependency_results=dependency_results,
                    message=message,
                    code=code,
                )
                execution_runs[step_id] = execution_run
                remaining_steps.pop(step_id)

            if invalid_steps or blocked_steps:
                continue

            ready_steps = [
                step
                for step in remaining_steps.values()
                if all(
                    dependency_id in execution_runs_by_id
                    for dependency_id in step.get("depends_on") or []
                )
            ]
            if ready_steps:
                step_outputs = await asyncio.gather(
                    *(
                        execute_step(step, dependency_inputs(step, execution_runs_by_id))
                        for step in ready_steps
                    )
                )
                for step, execution_run in zip(ready_steps, step_outputs):
                    step_id = str(step.get("task_id") or "")
                    execution_runs[step_id] = execution_run
                    remaining_steps.pop(step_id)
                continue

            for step_id, step in list(remaining_steps.items()):
                execution_run = build_blocked_run(
                    step,
                    dependency_results=dependency_inputs(step, execution_runs_by_id),
                    message="任务计划存在循环依赖，当前步骤无法调度。",
                    code="CYCLIC_DEPENDENCY",
                )
                execution_runs[step_id] = execution_run
                remaining_steps.pop(step_id)
        log_node_info(
            workflow_id="agent",
            node_id="execute",
            node_name="执行任务",
            details={
                "执行模式": execution_mode,
                "执行步骤数": len(execution_runs),
                "成功数": len(
                    [run for run in execution_runs.values() if run.get("status") == "success"]
                ),
                "失败数": len(
                    [run for run in execution_runs.values() if run.get("status") != "success"]
                ),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        return {"executions": execution_runs}

    return execute_node
