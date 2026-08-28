"""Standard result contract returned by executable task handlers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict


class TaskResultSummary(TypedDict, total=False):
    """Human-meaningful result summary for orchestration and final response."""

    title: str
    message: str
    confidence: float


class TaskResultData(TypedDict, total=False):
    """Structured task payload."""

    kind: str
    content: Any
    normalized: Any


class TaskResultEvidence(TypedDict, total=False):
    """Traceable evidence used by the handler."""

    citations: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    reasoning_trace: List[Dict[str, Any]]


class TaskResultActions(TypedDict, total=False):
    """Actions requested or suggested by the handler."""

    suggested_next_steps: List[Dict[str, Any]]
    required_user_input: List[Dict[str, Any]]
    approval_request: Dict[str, Any]


class TaskResultError(TypedDict, total=False):
    """Normalized handler error."""

    code: str
    message: str
    retryable: bool
    details: Dict[str, Any]


class TaskResultMeta(TypedDict, total=False):
    """Operational metadata for observability and protocol governance."""

    started_at: str
    finished_at: str
    latency_ms: int
    model: str
    token_usage: Dict[str, Any]
    version: str


class TaskResult(TypedDict, total=False):
    """Stable contract returned by a task handler to the main graph."""

    result_id: str
    handler_id: str
    run_id: str
    status: str
    answer_status: str
    summary: TaskResultSummary
    data: TaskResultData
    evidence: TaskResultEvidence
    actions: TaskResultActions
    errors: List[TaskResultError]
    meta: TaskResultMeta


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result_id(state: dict[str, Any], handler_id: str) -> str:
    run_id = str(state.get("run_id") or "run").strip()
    step_id = str((state.get("metadata") or {}).get("parent_task_id") or "task").strip()
    return f"{handler_id}:{run_id}:{step_id}"


def build_task_result(
    state: dict[str, Any],
    *,
    handler_id: str,
    status: str,
    answer_status: str,
    title: str,
    message: str,
) -> TaskResult:
    return {
        "result_id": _result_id(state, handler_id),
        "handler_id": handler_id,
        "run_id": str(state.get("run_id") or ""),
        "status": status,
        "answer_status": answer_status,
        "summary": {
            "title": title,
            "message": message,
        },
        "actions": {
            "suggested_next_steps": [],
            "required_user_input": [],
        },
        "errors": [],
        "meta": {
            "finished_at": _utc_now(),
            "version": "task_result.v1",
        },
    }


def build_failed_task_result(
    *,
    handler_id: str,
    run_id: str | None,
    step_id: str | None,
    message: str,
) -> TaskResult:
    state = {
        "run_id": run_id,
        "metadata": {"parent_task_id": step_id},
    }
    result = build_task_result(
        state,
        handler_id=handler_id,
        status="failed",
        answer_status="failed",
        title="任务处理失败",
        message=message,
    )
    result["data"] = {
        "kind": "mixed",
        "content": {},
    }
    result["evidence"] = {
        "citations": [],
        "sources": [],
        "reasoning_trace": [],
    }
    result["errors"] = [
        {
            "code": "TASK_HANDLER_EXECUTION_FAILED",
            "message": message,
            "retryable": False,
            "details": {"step_id": step_id},
        }
    ]
    return result
