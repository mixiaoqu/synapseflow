"""校验和并行执行本轮能力调用，结果反馈给主 Agent。"""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from time import monotonic
from typing import Any

from langchain_core.messages import ToolMessage
from loguru import logger
from pydantic import ValidationError

from app.agents.common.execution_budget import (
    AgentLimits,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    execution_budget,
)
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.common.task_result import build_failed_task_result
from app.agents.main.nodes.utils import (
    emit_subgraph_node_complete,
    forward_subgraph_custom_event,
    knowledge_diagnostics,
    parse_stream_chunk,
)
from app.agents.main.result import aggregate_execution_results, build_model_result
from app.agents.main.state import AgentState
from app.agents.runtime.tools import AgentToolDefinition, ToolArguments


def call_signature(name: str, arguments: dict[str, Any]) -> str:
    return json.dumps([name, arguments], ensure_ascii=False, sort_keys=True)


def build_execute_node(
    *,
    tools: tuple[AgentToolDefinition, ...],
    tool_workflows: dict[str, Any],
    limits: AgentLimits,
):
    definitions = {tool.name: tool for tool in tools}

    async def execute_node(state: AgentState) -> dict[str, Any]:
        calls = list(state["pending_calls"])
        previous = dict(state.get("executions") or {})
        writer = get_optional_stream_writer()
        semaphore = asyncio.Semaphore(limits.max_parallel)
        budget = ExecutionBudget(
            limits.max_operations, state["deadline"], int(state.get("operation_count") or 0)
        )
        signatures = {
            call_signature(run["tool_name"], run["arguments"]): call_id
            for call_id, run in previous.items()
            if not run.get("reused_from")
        }
        jobs: dict[str, asyncio.Task] = {}

        def failed(call, code, message):
            definition = definitions.get(call["name"])
            result = build_failed_task_result(
                handler_id=definition.workflow_id if definition else "unavailable",
                run_id=state["input"]["run_id"],
                step_id=call["id"],
                message=message,
            )
            result["errors"] = [{"code": code, "message": message, "retryable": False}]
            return {
                "call_id": call["id"],
                "tool_name": call["name"],
                "arguments": call["args"],
                "goal": call["args"].get("goal", ""),
                "status": "failed",
                "task_result": result,
                "diagnostics": {},
            }

        async def invoke(call, definition, arguments):
            async with semaphore:
                try:
                    budget.consume()
                    dependency_results = {
                        ref: deepcopy(previous[ref]["task_result"])
                        for ref in arguments["result_ids"]
                    }
                    child_input = definition.input_builder(
                        state,
                        {
                            **arguments,
                            "call_id": call["id"],
                            "dependency_results": dependency_results,
                        },
                    )
                    child_state: dict[str, Any] = {}

                    def scoped_writer(event):
                        if writer:
                            writer(
                                {
                                    **event,
                                    "tool_call_id": call["id"],
                                    "round": state["decision_count"],
                                }
                            )

                    async def run_child():
                        async for chunk in tool_workflows[definition.name].astream(
                            child_input, stream_mode=["updates", "custom"], version="v2"
                        ):
                            kind, data = parse_stream_chunk(chunk)
                            if kind == "custom":
                                forward_subgraph_custom_event(
                                    scoped_writer, definition.workflow_id, data
                                )
                            elif kind == "updates":
                                for node_id, update in data.items():
                                    if isinstance(update, dict):
                                        child_state.update(update)
                                        emit_subgraph_node_complete(
                                            scoped_writer, definition.workflow_id, node_id, update
                                        )

                    emit_activity(
                        writer,
                        workflow_id="agent",
                        node_id="execute",
                        stage="execute",
                        message="正在执行能力调用",
                        display_stage="execute",
                        display_title="执行任务",
                        activity_text=arguments["goal"],
                        tool_call_id=call["id"],
                        round=state["decision_count"],
                    )
                    with execution_budget(budget):
                        await asyncio.wait_for(
                            run_child(),
                            timeout=min(
                                limits.call_timeout, max(0.01, budget.deadline - monotonic())
                            ),
                        )
                    result = child_state.get("task_result")
                    if not isinstance(result, dict) or not result.get("status"):
                        raise ValueError("能力工具结束时缺少有效结果")
                    return {
                        "call_id": call["id"],
                        "tool_name": definition.name,
                        "arguments": arguments,
                        "goal": arguments["goal"],
                        "handler_id": definition.workflow_id,
                        "status": result["status"],
                        "result_ids": arguments["result_ids"],
                        "task_result": result,
                        "diagnostics": knowledge_diagnostics(child_state),
                    }
                except ExecutionBudgetExceededError:
                    return failed(call, "EXECUTION_BUDGET_EXHAUSTED", "本次任务已达到执行预算。")
                except TimeoutError:
                    return failed(call, "TOOL_TIMEOUT", "本次能力调用超时。")
                except Exception:
                    logger.exception("能力工具执行失败：{}", definition.name)
                    return failed(call, "TOOL_EXECUTION_FAILED", "本次能力调用发生异常。")

        async def resolve_call(call, index):
            definition = definitions.get(call["name"])
            if definition is None or not definition.available(state["input"]):
                return failed(call, "TOOL_UNAVAILABLE", "当前请求无法使用该能力。")
            try:
                arguments = ToolArguments.model_validate(call["args"]).model_dump()
            except ValidationError:
                return failed(call, "INVALID_TOOL_ARGUMENTS", "工具输入需符合已提供的参数定义。")
            if any(ref not in previous for ref in arguments["result_ids"]):
                return failed(call, "UNKNOWN_RESULT", "结果引用必须来自已完成的调用。")
            # 重用引用统一到原始调用，避免仅更换引用 ID 导致重复执行。
            arguments["result_ids"] = sorted(
                {previous[ref].get("reused_from", ref) for ref in arguments["result_ids"]}
            )
            signature = call_signature(definition.name, arguments)
            if signature in signatures:
                original = previous[signatures[signature]]
                return {**original, "call_id": call["id"], "reused_from": original["call_id"]}
            if signature in jobs:
                original = await jobs[signature]
                return {**original, "call_id": call["id"], "reused_from": original["call_id"]}
            if len(previous) + index >= limits.max_calls:
                return failed(call, "TOOL_CALL_LIMIT", "本次任务已达到能力调用次数上限。")
            jobs[signature] = asyncio.create_task(invoke(call, definition, arguments))
            return await jobs[signature]

        async def resolve(call, index):
            output = await resolve_call(call, index)
            emit_activity(
                writer,
                workflow_id="agent",
                node_id="execute",
                stage="execute",
                message="能力调用已结束",
                display_stage="execute",
                display_title="执行任务",
                activity_text=output["task_result"]["summary"]["message"],
                activity_status="error" if output["status"] == "failed" else "completed",
                tool_call_id=call["id"],
                round=state["decision_count"],
            )
            return output

        outputs = await asyncio.gather(*(resolve(call, i) for i, call in enumerate(calls)))
        executions = {**previous, **{run["call_id"]: run for run in outputs}}
        messages = [
            *list(state.get("messages") or []),
            *[
                ToolMessage(
                    tool_call_id=run["call_id"],
                    name=run["tool_name"],
                    content=json.dumps(
                        build_model_result(run),
                        ensure_ascii=False,
                        default=str,
                    ),
                )
                for run in outputs
            ],
        ]
        return {
            "pending_calls": [],
            "executions": executions,
            "messages": messages,
            "operation_count": budget.used,
            "result": aggregate_execution_results(
                {key: value for key, value in executions.items() if not value.get("reused_from")}
            ),
        }

    return execute_node
