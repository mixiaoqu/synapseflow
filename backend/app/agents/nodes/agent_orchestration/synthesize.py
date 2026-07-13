"""Synthesize node for top-level agent orchestration."""

from __future__ import annotations

from typing import Any

from app.agents.common.node_logging import log_node_info
from app.agents.states import AgentState


def build_synthesized_result(collected_results: dict[str, Any]) -> dict[str, Any]:
    success_count = int(collected_results.get("success_count") or 0)
    failed_count = int(collected_results.get("failed_count") or 0)
    needs_input_count = int(collected_results.get("needs_input_count") or 0)
    if success_count and (failed_count or needs_input_count):
        final_status = "partial"
        answer_status = "partial"
    elif needs_input_count:
        final_status = "clarification_needed"
        answer_status = "clarification_needed"
    elif success_count:
        final_status = "answered"
        answer_status = "answered"
    else:
        final_status = "failed"
        answer_status = "failed"

    return {
        "final_status": final_status,
        "answer_status": answer_status,
        "knowledge_context": list(collected_results.get("knowledge_context") or []),
        "business_data": list(collected_results.get("business_data") or []),
        "citation_refs": list(collected_results.get("citation_refs") or []),
        "errors": list(collected_results.get("errors") or []),
        "clarifications": list(collected_results.get("clarifications") or []),
        "user_action_required": ("clarify" if collected_results.get("clarifications") else None),
    }


def aggregate_workflow_result(
    synthesized_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "workflow_id": "agent",
        "status": synthesized_result.get("final_status") or "failed",
        "answer_status": synthesized_result.get("answer_status") or "failed",
        "citation_refs": list(synthesized_result.get("citation_refs") or []),
        "payload": {
            "errors": list(synthesized_result.get("errors") or []),
            "clarifications": list(synthesized_result.get("clarifications") or []),
        },
    }


async def synthesize_node(state: AgentState) -> dict[str, Any]:
    collected_results = dict(state.get("collected_results") or {})
    synthesized_result = build_synthesized_result(collected_results)
    workflow_result = aggregate_workflow_result(synthesized_result)
    log_node_info(
        workflow_id="agent",
        node_id="synthesize",
        node_name="整编结果",
        details={
            "最终状态": synthesized_result.get("final_status"),
            "回答状态": synthesized_result.get("answer_status"),
            "引用数": len(synthesized_result.get("citation_refs") or []),
            "错误数": len(synthesized_result.get("errors") or []),
        },
    )
    return {
        "synthesized_result": synthesized_result,
        "workflow_result": workflow_result,
        "answer_status": synthesized_result.get("answer_status") or "failed",
        "retrieved_docs": list(collected_results.get("retrieved_docs") or []),
        "backend_citations": list(collected_results.get("retrieved_docs") or []),
    }
