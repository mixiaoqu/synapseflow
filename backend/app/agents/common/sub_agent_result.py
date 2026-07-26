"""Standard result contract returned by executable sub-agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict


class SubAgentSummary(TypedDict, total=False):
    """Human-meaningful result summary for orchestration and final response."""

    title: str
    message: str
    confidence: float


class SubAgentData(TypedDict, total=False):
    """Structured sub-agent payload."""

    kind: str
    content: Any
    normalized: Any


class SubAgentEvidence(TypedDict, total=False):
    """Traceable evidence used by the sub-agent."""

    citations: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    reasoning_trace: List[Dict[str, Any]]


class SubAgentActions(TypedDict, total=False):
    """Actions requested or suggested by the sub-agent."""

    suggested_next_steps: List[Dict[str, Any]]
    required_user_input: List[Dict[str, Any]]
    approval_request: Dict[str, Any]


class SubAgentError(TypedDict, total=False):
    """Normalized sub-agent error."""

    code: str
    message: str
    retryable: bool
    details: Dict[str, Any]


class SubAgentMeta(TypedDict, total=False):
    """Operational metadata for observability and protocol governance."""

    started_at: str
    finished_at: str
    latency_ms: int
    model: str
    token_usage: Dict[str, Any]
    version: str


class SubAgentResult(TypedDict, total=False):
    """Stable contract returned by child sub-agents to the main agent graph."""

    result_id: str
    sub_agent_id: str
    run_id: str
    status: str
    answer_status: str
    summary: SubAgentSummary
    data: SubAgentData
    evidence: SubAgentEvidence
    actions: SubAgentActions
    errors: List[SubAgentError]
    meta: SubAgentMeta


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result_id(state: dict[str, Any], sub_agent_id: str) -> str:
    run_id = str(state.get("run_id") or "run").strip()
    step_id = str((state.get("metadata") or {}).get("parent_step_id") or "step").strip()
    return f"{sub_agent_id}:{run_id}:{step_id}"


def build_sub_agent_result(
    state: dict[str, Any],
    *,
    sub_agent_id: str,
    status: str,
    answer_status: str,
    title: str,
    message: str,
) -> SubAgentResult:
    return {
        "result_id": _result_id(state, sub_agent_id),
        "sub_agent_id": sub_agent_id,
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
            "version": "sub_agent_result.v1",
        },
    }


def build_failed_sub_agent_result(
    *,
    sub_agent_id: str,
    run_id: str | None,
    step_id: str | None,
    message: str,
) -> SubAgentResult:
    state = {
        "run_id": run_id,
        "metadata": {"parent_step_id": step_id},
    }
    result = build_sub_agent_result(
        state,
        sub_agent_id=sub_agent_id,
        status="failed",
        answer_status="failed",
        title="子智能体执行失败",
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
            "code": "SUB_AGENT_EXECUTION_FAILED",
            "message": message,
            "retryable": False,
            "details": {"step_id": step_id},
        }
    ]
    return result
