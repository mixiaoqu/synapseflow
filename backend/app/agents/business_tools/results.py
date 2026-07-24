"""Deterministic aggregation of sequential tool execution results."""

from __future__ import annotations

from app.agents.business_tools.schemas import ToolDecision, ToolRunResult, ToolRunStatus, ToolStep


def build_tool_run_result(*, decision: ToolDecision, steps: list[ToolStep]) -> ToolRunResult:
    successful = [step for step in steps if step.status == "success"]
    failed = [step for step in steps if step.status == "failed"]

    if successful and failed:
        status: ToolRunStatus = "partial_success"
    elif failed:
        status = "failed"
    elif decision.action == "complete" and successful:
        status = "success"
    elif decision.action == "clarify":
        status = "needs_input"
    elif decision.action == "limit_reached":
        status = "limit_reached"
    else:
        status = "unsupported"

    defaults = {
        "success": "业务数据查询已完成。",
        "partial_success": "已取得部分业务数据，但后续查询未完成。",
        "needs_input": "还需要补充必要信息。",
        "unsupported": "当前没有能够完成该请求的业务工具。",
        "failed": "业务工具调用失败。",
        "limit_reached": "已达到业务工具调用次数上限。",
    }
    return ToolRunResult(
        status=status,
        message=decision.message or defaults[status],
        steps=steps,
        successful_data=[step.data or {} for step in successful],
    )
