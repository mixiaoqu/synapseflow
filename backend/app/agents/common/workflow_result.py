"""Structured workflow results passed from subgraphs to the top-level responder."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class AgentEvidence(TypedDict, total=False):
    """Evidence collected by a child workflow."""

    kind: str
    status: str
    data: Dict[str, Any]
    citations: List[Dict[str, Any]]


class WorkflowResult(TypedDict, total=False):
    """Stable contract returned by child workflows before final response generation."""

    workflow_id: str
    status: str
    evidence: AgentEvidence
    payload: Dict[str, Any]
    answer_status: str


def build_knowledge_workflow_result(state: dict[str, Any]) -> WorkflowResult:
    retrieved_docs = list(state.get("retrieved_docs") or [])
    retrieval_trace = dict(state.get("retrieval_trace") or {})
    evidence = dict(state.get("evidence") or {})
    status = "found" if retrieved_docs else "empty"
    return {
        "workflow_id": "knowledge_qa",
        "status": status,
        "answer_status": "answered" if retrieved_docs else "no_relevant_context",
        "evidence": {
            "kind": "knowledge",
            "status": status,
            "citations": retrieved_docs,
            "data": {
                "primary_context": state.get("primary_context") or "",
                "supporting_context": state.get("supporting_context") or "",
                "context": state.get("context") or "",
                "retrieved_docs": retrieved_docs,
                "retrieval": dict(state.get("retrieval") or {}),
                "retrieval_trace": retrieval_trace,
                "evidence": evidence,
            },
        },
        "payload": {
            "retrieval_analysis": dict(state.get("retrieval_analysis") or {}),
            "retrieval": dict(state.get("retrieval") or {}),
            "retrieval_trace": retrieval_trace,
        },
    }


def build_business_workflow_result(state: dict[str, Any]) -> WorkflowResult:
    operation_result = dict(state.get("business_operation_result") or {})
    success = bool(operation_result.get("success"))
    error = dict(operation_result.get("error") or {})
    status = "success" if success else "failed"
    return {
        "workflow_id": "business_ops",
        "status": status,
        "answer_status": "answered" if success else "tool_failed",
        "evidence": {
            "kind": "business",
            "status": status,
            "citations": [],
            "data": {
                "business_request": dict(state.get("business_request") or {}),
                "business_operation": dict(state.get("business_operation") or {}),
                "business_operation_result": operation_result,
                "business_result": dict(state.get("business_result") or {}),
            },
        },
        "payload": {
            "message": operation_result.get("message") or error.get("message") or "",
            "error": error,
            "operation_id": operation_result.get("operation_id"),
        },
    }
