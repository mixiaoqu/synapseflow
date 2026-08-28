"""Shared helpers for top-level Agent nodes."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from app.core.llm import get_llm


def parse_stream_chunk(chunk: Any) -> tuple[str | None, dict[str, Any]]:
    if isinstance(chunk, tuple) and len(chunk) == 2:
        mode, data = chunk
        if isinstance(mode, str) and isinstance(data, dict):
            return mode, data
        return None, {}
    if isinstance(chunk, dict):
        chunk_type = chunk.get("type")
        chunk_data = chunk.get("data", {})
        if isinstance(chunk_type, str) and isinstance(chunk_data, dict):
            return chunk_type, chunk_data
    return None, {}


def coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content or "")


def json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, indent=2)


def normalize_query(query: Any) -> str:
    return re.sub(r"\s+", " ", str(query or "").strip())


def forward_subgraph_custom_event(
    writer: Callable[[dict[str, Any]], None] | None,
    workflow_id: str,
    data: dict[str, Any],
) -> None:
    if writer is None:
        return
    event_workflow_id = str(data.get("workflow_id") or "").strip()
    if not event_workflow_id:
        raise ValueError("Subgraph custom event is missing workflow_id")
    if event_workflow_id != workflow_id:
        raise ValueError(
            "Subgraph custom event workflow_id mismatch: "
            f"expected={workflow_id} actual={event_workflow_id}"
        )
    writer(dict(data))


def emit_subgraph_node_complete(
    writer: Callable[[dict[str, Any]], None] | None,
    workflow_id: str,
    node_id: str,
    node_state: dict[str, Any],
) -> None:
    if writer is None:
        return
    writer(
        {
            "type": "node_complete",
            "workflow_id": workflow_id,
            "node_id": node_id,
            "node_state": node_state,
        }
    )


def get_answer_llm(
    state: dict[str, Any],
    llm_factory: Callable[[], Any] | None,
) -> Any:
    if llm_factory is not None:
        return llm_factory()
    model_key = str(state.get("assistant_llm_model_key") or "generation").strip()
    return get_llm(model_key or "generation")


def knowledge_diagnostics(child_state: dict[str, Any]) -> dict[str, Any]:
    if not child_state.get("retrieval_analysis"):
        return {}
    retrieval_analysis = dict(child_state.get("retrieval_analysis") or {})
    retrieval_result = dict(child_state.get("retrieval_result") or {})
    return {
        "goal": child_state.get("query"),
        "normalized_query": child_state.get("normalized_query"),
        "retrieval_profile": child_state.get("retrieval_profile"),
        "route_reason": retrieval_analysis.get("reason"),
        "retrieval_execution_plan": dict(child_state.get("retrieval_execution_plan") or {}),
        "query_plan_attempt": int(child_state.get("query_plan_attempt") or 1),
        "retrieval_feedback": dict(child_state.get("retrieval_feedback") or {}),
        "retrieval_attempts": list(child_state.get("retrieval_attempts") or []),
        "semantic_queries": list(child_state.get("semantic_queries") or []),
        "lexical_terms": list(child_state.get("lexical_terms") or []),
        "query_plan_trace": dict(child_state.get("query_plan_trace") or {}),
        "retrieval_status": retrieval_result.get("status"),
        "retrieval_reason_code": retrieval_result.get("reason_code"),
        "retrieval_budget": dict(retrieval_result.get("budget") or {}),
        "retrieval_metrics": dict(retrieval_result.get("metrics") or {}),
        "retrieval_warnings": list(retrieval_result.get("warnings") or []),
    }
