"""Build the standard result returned by the business operations workflow."""

from __future__ import annotations

from typing import Any

from app.agents.business_ops.tools.results import build_tool_run_result
from app.agents.business_ops.tools.schemas import ToolDecision, ToolStep
from app.agents.common.sub_agent_result import (
    SubAgentResult,
    build_sub_agent_result,
)


def build_business_sub_agent_result(state: dict[str, Any]) -> SubAgentResult:
    operation_result = dict(state.get("business_operation_result") or {})
    business_request = dict(state.get("business_request") or {})
    success = bool(operation_result.get("success"))
    error = dict(operation_result.get("error") or {})
    retryable = bool(error.get("retryable"))
    request_status = str(business_request.get("status") or "unsupported")
    clarification_message = str(business_request.get("clarification") or "").strip()
    decision = ToolDecision(
        action={
            "complete": "complete",
            "clarification_required": "clarify",
            "limit_reached": "limit_reached",
        }.get(request_status, "unsupported"),
        clarification_question=(
            clarification_message or None
            if request_status == "clarification_required"
            else None
        ),
        reason=str(business_request.get("reason") or "").strip() or None,
    )
    steps = [
        ToolStep(
            index=int(item.get("index") or index),
            tool_id=str(item.get("tool_id") or ""),
            arguments=dict(item.get("arguments") or {}),
            status=str(item.get("status") or "failed"),
            data=dict(item.get("data") or {}),
            error=item.get("error"),
            duration_ms=item.get("duration_ms"),
        )
        for index, item in enumerate(state.get("business_call_history") or [], start=1)
    ]
    run_result = build_tool_run_result(decision=decision, steps=steps)
    status = run_result.status
    if request_status == "clarification_required":
        status = "needs_input"
    elif request_status in {"planner_failed", "repair_failed"}:
        status = "failed"
    answer_status = {
        "success": "answered",
        "partial_success": "partial",
        "needs_input": "clarification_needed",
    }.get(status, "failed")
    message = (
        clarification_message
        if request_status == "clarification_required"
        else str(operation_result.get("message") or "").strip()
        or str(error.get("message") or "").strip()
        or str(business_request.get("reason") or "").strip()
        or "业务操作子智能体执行完成。"
    )
    result = build_sub_agent_result(
        state,
        sub_agent_id="business_ops",
        status=status,
        answer_status=answer_status,
        title="业务操作子智能体结果",
        message=message,
    )
    result["data"] = {
        "kind": "action_result",
        "content": dict(state.get("business_result") or {}),
        "normalized": {
            "business_request": business_request,
            "business_operation": dict(state.get("business_operation") or {}),
            "business_operation_result": operation_result,
        },
    }
    result["evidence"] = {
        "citations": [],
        "sources": [],
        "reasoning_trace": [
            {
                "stage": "business_operation",
                "status": status,
                "data": {
                    "operation_id": operation_result.get("operation_id"),
                    "success": success,
                },
            }
        ],
    }
    if status == "needs_input":
        result["actions"]["required_user_input"] = [
            {
                "kind": "clarification",
                "operation_id": operation_result.get("operation_id"),
                "message": message,
            }
        ]
    if status not in {"success", "needs_input"}:
        result["errors"] = [
            {
                "code": str(error.get("code") or business_request.get("status") or "FAILED"),
                "message": message,
                "retryable": retryable,
                "details": {
                    "operation_id": operation_result.get("operation_id"),
                    "raw_error": error,
                },
            }
        ]
    return result

