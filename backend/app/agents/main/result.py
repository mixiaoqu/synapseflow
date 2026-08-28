"""Aggregate child execution results into one platform result."""

from __future__ import annotations

from typing import Any


def _source_identity(item: dict[str, Any]) -> str:
    source = dict(item.get("source") or {})
    if source.get("source_type") == "web" and source.get("url"):
        return f"web:{source['url']}"
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


def build_model_result(run: dict[str, Any]) -> dict[str, Any]:
    """为决策和最终回答提供同一份结果契约，保持业务载荷原样传递。"""
    return {
        "result_id": run["call_id"],
        "goal": run["goal"],
        "reused_from": run.get("reused_from"),
        "result": {
            key: value
            for key, value in run["task_result"].items()
            if key
            in {"status", "answer_status", "summary", "data", "evidence", "actions", "errors"}
        },
    }


def aggregate_execution_results(execution_runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    runs = list(execution_runs.values())
    task_results = [
        dict(run.get("task_result") or {})
        for run in runs
        if isinstance(run.get("task_result"), dict)
    ]
    successes = [
        result for result in task_results if result.get("status") in {"success", "partial_success"}
    ]
    needs_input = [result for result in task_results if result.get("status") == "needs_input"]
    failures = [
        result
        for result in task_results
        if result.get("status") not in {"success", "partial_success", "needs_input"}
    ]
    has_partial_success = any(
        result.get("status") == "partial_success" or result.get("answer_status") == "partial"
        for result in successes
    )
    knowledge_context: list[dict[str, Any]] = []
    web_context: list[dict[str, Any]] = []
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
                    "call_id": run.get("call_id"),
                    "goal": run.get("goal"),
                    **diagnostics,
                }
            )
    for task_result in task_results:
        data = dict(task_result.get("data") or {})
        content = data.get("content")
        if data.get("kind") == "document" and isinstance(content, dict):
            knowledge_context.extend(
                dict(item)
                for item in list(content.get("knowledge_context") or [])
                if isinstance(item, dict)
            )
        elif data.get("kind") == "web" and isinstance(content, dict):
            web_context.extend(
                dict(item) for item in list(content.get("web_context") or [])
                if isinstance(item, dict)
            )
        elif data.get("kind") == "action_result" and isinstance(content, dict):
            business_data.append(
                {
                    "handler_id": task_result.get("handler_id"),
                    "content": dict(content),
                }
            )
        evidence = dict(task_result.get("evidence") or {})
        citation_refs.extend(
            str(item.get("ref_id") or "").strip()
            for item in list(evidence.get("citations") or [])
            if isinstance(item, dict) and str(item.get("ref_id") or "").strip()
        )
        actions = dict(task_result.get("actions") or {})
        clarifications.extend(list(actions.get("required_user_input") or []))
        result_errors.extend(
            {
                "handler_id": task_result.get("handler_id"),
                "code": item.get("code"),
                "message": item.get("message"),
                "retryable": bool(item.get("retryable")),
            }
            for item in list(task_result.get("errors") or [])
            if isinstance(item, dict)
        )

    context_by_ref: dict[str, dict[str, Any]] = {}
    for item in [*knowledge_context, *web_context]:
        ref_id = str(item.get("ref_id") or "").strip()
        if ref_id and (
            ref_id not in context_by_ref
            or (
                item.get("kind") == "web_page"
                and item.get("role") == "primary"
                and context_by_ref[ref_id].get("role") != "primary"
            )
        ):
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
            if key not in {"call_id", "goal"}
        }
        if knowledge_goal_diagnostics
        else {}
    )
    aggregated_errors = result_errors or [
        {
            "handler_id": result.get("handler_id"),
            "code": "TASK_HANDLER_FAILED",
            "message": result.get("summary"),
            "retryable": False,
        }
        for result in failures
    ]
    answer_material = {"tool_results": [build_model_result(run) for run in runs]}
    return {
        **primary_knowledge_diagnostics,
        "knowledge_goal_diagnostics": knowledge_goal_diagnostics,
        "status": status,
        "answer_status": answer_status,
        "success_count": len(successes),
        "failed_count": len(failures),
        "needs_input_count": len(needs_input),
        "partial": bool(successes and (failures or needs_input or has_partial_success)),
        "knowledge_context": [
            item for item in context_by_ref.values()
            if item.get("kind") not in {"web_page", "web_snippet"}
        ],
        "web_context": [
            item for item in context_by_ref.values()
            if item.get("kind") in {"web_page", "web_snippet"}
        ],
        "business_data": business_data,
        "citation_refs": deduped_citation_refs,
        "sources": retrieved_docs,
        "errors": aggregated_errors,
        "clarifications": clarifications,
        "answer_material": answer_material,
    }
