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


def _base_result(
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


def build_knowledge_sub_agent_result(state: dict[str, Any]) -> SubAgentResult:
    retrieved_docs = list(state.get("retrieved_docs") or [])
    retrieval_trace = dict(state.get("retrieval_trace") or {})
    evidence = dict(state.get("evidence") or {})
    status = "success" if retrieved_docs else "failed"
    answer_status = "answered" if retrieved_docs else "no_answer"
    message = (
        f"已找到 {len(retrieved_docs)} 条相关知识证据。"
        if retrieved_docs
        else "当前知识库没有找到可用于回答的相关内容。"
    )
    result = _base_result(
        state,
        sub_agent_id="knowledge_qa",
        status=status,
        answer_status=answer_status,
        title="知识问答子智能体结果",
        message=message,
    )
    result["data"] = {
        "kind": "document",
        "content": {
            "primary_context": state.get("primary_context") or "",
            "supporting_context": state.get("supporting_context") or "",
            "context": state.get("context") or "",
            "retrieved_docs": retrieved_docs,
        },
        "normalized": {
            "retrieval": dict(state.get("retrieval") or {}),
            "retrieval_trace": retrieval_trace,
            "evidence": evidence,
        },
    }
    result["evidence"] = {
        "citations": retrieved_docs,
        "sources": retrieved_docs,
        "reasoning_trace": [
            {
                "stage": "retrieval",
                "status": "found" if retrieved_docs else "empty",
                "data": {
                    "retrieval_analysis": dict(state.get("retrieval_analysis") or {}),
                    "retrieval": dict(state.get("retrieval") or {}),
                    "retrieval_trace": retrieval_trace,
                },
            }
        ],
    }
    return result


def build_business_sub_agent_result(state: dict[str, Any]) -> SubAgentResult:
    operation_result = dict(state.get("business_operation_result") or {})
    business_request = dict(state.get("business_request") or {})
    success = bool(operation_result.get("success"))
    error = dict(operation_result.get("error") or {})
    retryable = bool(error.get("retryable"))
    status = "success" if success else ("needs_input" if retryable else "failed")
    answer_status = "answered" if success else ("clarification_needed" if retryable else "failed")
    message = (
        str(operation_result.get("message") or "").strip()
        or str(error.get("message") or "").strip()
        or str(business_request.get("reason") or "").strip()
        or "业务操作子智能体执行完成。"
    )
    result = _base_result(
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
    if retryable:
        result["actions"]["required_user_input"] = [
            {
                "kind": "clarification",
                "operation_id": operation_result.get("operation_id"),
                "message": message,
            }
        ]
    if not success:
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
    result = _base_result(
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
