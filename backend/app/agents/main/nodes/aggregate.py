"""Aggregate child execution results into one platform result."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agents.common.node_logging import log_node_info
from app.agents.main.state import AgentState


def _source_identity(item: dict[str, Any]) -> str:
    source = dict(item.get("source") or {})
    ref_id = str(item.get("ref_id") or "").strip()
    if ref_id:
        return f"ref:{ref_id}"
    parent_chunk_id = source.get("parent_chunk_id")
    if parent_chunk_id is not None:
        return f"parent:{parent_chunk_id}"
    document_chunk_id = source.get("document_chunk_id")
    if document_chunk_id is not None:
        return f"chunk:{document_chunk_id}"
    document_id = source.get("document_id")
    if document_id is not None:
        return f"document:{document_id}"

    document_title = str(source.get("document_title") or "").strip().casefold()
    if document_title:
        return f"title:{document_title}"

    return f"content:{str(item.get('content') or '').strip().casefold()}"


def aggregate_execution_results(execution_runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    runs = list(execution_runs.values())
    sub_agent_results = [
        dict(run.get("sub_agent_result") or {})
        for run in runs
        if isinstance(run.get("sub_agent_result"), dict)
    ]
    successes = [result for result in sub_agent_results if result.get("status") == "success"]
    needs_input = [result for result in sub_agent_results if result.get("status") == "needs_input"]
    failures = [
        result
        for result in sub_agent_results
        if result.get("status") not in {"success", "needs_input"}
    ]
    has_partial_success = any(
        result.get("answer_status") == "partial" for result in successes
    )
    knowledge_context: list[dict[str, Any]] = []
    citation_refs: list[str] = []
    business_data: list[dict[str, Any]] = []
    clarifications: list[dict[str, Any]] = []
    result_errors: list[dict[str, Any]] = []
    knowledge_goal_diagnostics: list[dict[str, Any]] = []
    for run in runs:
        diagnostics = dict(run.get("diagnostics") or {})
        if diagnostics:
            knowledge_goal_diagnostics.append(
                {
                    "task_id": run.get("task_id"),
                    "goal": run.get("goal"),
                    **diagnostics,
                }
            )
    for sub_agent_result in sub_agent_results:
        data = dict(sub_agent_result.get("data") or {})
        content = data.get("content")
        if data.get("kind") == "document" and isinstance(content, dict):
            knowledge_context.extend(
                dict(item)
                for item in list(content.get("knowledge_context") or [])
                if isinstance(item, dict)
            )
        elif data.get("kind") == "action_result" and isinstance(content, dict):
            business_data.append(
                {
                    "sub_agent_id": sub_agent_result.get("sub_agent_id"),
                    "content": dict(content),
                }
            )
        evidence = dict(sub_agent_result.get("evidence") or {})
        citation_refs.extend(
            str(item.get("ref_id") or "").strip()
            for item in list(evidence.get("citations") or [])
            if isinstance(item, dict) and str(item.get("ref_id") or "").strip()
        )
        actions = dict(sub_agent_result.get("actions") or {})
        clarifications.extend(list(actions.get("required_user_input") or []))
        result_errors.extend(
            {
                "sub_agent_id": sub_agent_result.get("sub_agent_id"),
                "code": item.get("code"),
                "message": item.get("message"),
                "retryable": bool(item.get("retryable")),
            }
            for item in list(sub_agent_result.get("errors") or [])
            if isinstance(item, dict)
        )

    context_by_ref: dict[str, dict[str, Any]] = {}
    for item in knowledge_context:
        ref_id = str(item.get("ref_id") or "").strip()
        if ref_id and ref_id not in context_by_ref:
            context_by_ref[ref_id] = item
    deduped_citation_refs = list(dict.fromkeys(citation_refs))

    retrieved_docs: list[dict[str, Any]] = []
    retrieved_source_ids: set[str] = set()
    for ref_id, item in context_by_ref.items():
        if item.get("role") != "primary":
            continue
        source_id = _source_identity(item)
        if source_id in retrieved_source_ids:
            continue
        retrieved_source_ids.add(source_id)
        retrieved_docs.append(
            {
                "content": item.get("content") or "",
                "metadata": {
                    **dict(item.get("source") or {}),
                    "ref_id": ref_id,
                    "role": item.get("role"),
                    "kind": item.get("kind"),
                },
            }
        )
    if successes and (failures or needs_input or has_partial_success):
        status = answer_status = "partial"
    elif needs_input:
        status = answer_status = "clarification_needed"
    elif successes:
        status = answer_status = "answered"
    else:
        status = answer_status = "failed"
    primary_knowledge_diagnostics = (
        {
            key: value
            for key, value in knowledge_goal_diagnostics[0].items()
            if key not in {"task_id", "goal"}
        }
        if knowledge_goal_diagnostics
        else {}
    )
    return {
        **primary_knowledge_diagnostics,
        "knowledge_goal_diagnostics": knowledge_goal_diagnostics,
        "status": status,
        "answer_status": answer_status,
        "success_count": len(successes),
        "failed_count": len(failures),
        "needs_input_count": len(needs_input),
        "partial": bool(successes and (failures or needs_input or has_partial_success)),
        "knowledge_context": list(context_by_ref.values()),
        "business_data": business_data,
        "citation_refs": deduped_citation_refs,
        "sources": retrieved_docs,
        "errors": result_errors
        or [
            {
                "sub_agent_id": result.get("sub_agent_id"),
                "code": "SUB_AGENT_FAILED",
                "message": result.get("summary"),
                "retryable": False,
            }
            for result in failures
        ],
        "clarifications": clarifications,
    }


async def aggregate_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    result = aggregate_execution_results(dict(state.get("executions") or {}))
    log_node_info(
        workflow_id="agent",
        node_id="aggregate",
        node_name="聚合结果",
        details={
            "状态": result.get("status"),
            "成功数": result.get("success_count"),
            "失败数": result.get("failed_count"),
            "引用数": len(result.get("citation_refs") or []),
        },
        elapsed_ms=int((perf_counter() - started_at) * 1000),
    )
    return {"result": result}
