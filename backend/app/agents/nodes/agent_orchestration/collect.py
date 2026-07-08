"""Collect node for top-level agent orchestration."""

from __future__ import annotations

from typing import Any

from app.agents.common.node_logging import log_node_info
from app.agents.states import AgentState


def collect_execution_results(execution_runs: list[dict[str, Any]]) -> dict[str, Any]:
    sub_agent_results = [
        dict(run.get("sub_agent_result") or {})
        for run in execution_runs
        if isinstance(run.get("sub_agent_result"), dict)
    ]
    successes = [result for result in sub_agent_results if result.get("status") == "success"]
    needs_input = [result for result in sub_agent_results if result.get("status") == "needs_input"]
    failures = [
        result
        for result in sub_agent_results
        if result.get("status") not in {"success", "needs_input"}
    ]
    citations: list[dict[str, Any]] = []
    clarifications: list[dict[str, Any]] = []
    result_errors: list[dict[str, Any]] = []
    for sub_agent_result in sub_agent_results:
        evidence = dict(sub_agent_result.get("evidence") or {})
        citations.extend(list(evidence.get("citations") or []))
        actions = dict(sub_agent_result.get("actions") or {})
        clarifications.extend(list(actions.get("required_user_input") or []))
        result_errors.extend(list(sub_agent_result.get("errors") or []))
    return {
        "task_results": execution_runs,
        "sub_agent_results": sub_agent_results,
        "success_count": len(successes),
        "failed_count": len(failures),
        "needs_input_count": len(needs_input),
        "partial": bool(successes and (failures or needs_input)),
        "citations": citations,
        "errors": result_errors
        or [
            {"sub_agent_id": result.get("sub_agent_id"), "error": result.get("summary")}
            for result in failures
        ],
        "clarifications": clarifications,
        "approvals": [],
    }


async def collect_node(state: AgentState) -> dict[str, Any]:
    collected_results = collect_execution_results(list(state.get("execution_runs") or []))
    log_node_info(
        workflow_id="agent",
        node_id="collect",
        node_name="收集结果",
        details={
            "成功数": collected_results.get("success_count"),
            "失败数": collected_results.get("failed_count"),
            "引用数": len(collected_results.get("citations") or []),
            "澄清数": len(collected_results.get("clarifications") or []),
        },
    )
    return {
        "collected_results": collected_results,
        "sub_agent_results": list(collected_results.get("sub_agent_results") or []),
        "retrieved_docs": list(collected_results.get("citations") or []),
        "backend_citations": list(collected_results.get("citations") or []),
    }
