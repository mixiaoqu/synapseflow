"""Build the standard result returned by the knowledge QA workflow."""

from __future__ import annotations

from typing import Any

from app.agents.common.sub_agent_result import (
    SubAgentResult,
    build_sub_agent_result,
)


def build_knowledge_sub_agent_result(state: dict[str, Any]) -> SubAgentResult:
    retrieval_result = dict(state.get("retrieval_result") or {})
    retrieval_status = str(retrieval_result.get("status") or "failed")
    evidence_items = [
        dict(item)
        for item in list(retrieval_result.get("evidence_items") or [])
        if isinstance(item, dict)
    ]
    primary_count = len([item for item in evidence_items if item.get("role") == "primary"])
    status = "success" if retrieval_status == "found" and primary_count else "failed"
    answer_status = "answered" if status == "success" else "no_answer"
    message = (
        f"已找到 {primary_count} 条主要知识证据。"
        if status == "success"
        else "当前知识库没有找到可用于回答的相关内容。"
    )
    result = build_sub_agent_result(
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
            "knowledge_context": evidence_items,
        },
        "normalized": {
            "retrieval_status": retrieval_status,
            "reason_code": retrieval_result.get("reason_code"),
            "budget": dict(retrieval_result.get("budget") or {}),
            "metrics": dict(retrieval_result.get("metrics") or {}),
            "warnings": list(retrieval_result.get("warnings") or []),
        },
    }
    result["evidence"] = {
        "citations": [
            {
                "ref_id": item.get("ref_id"),
                "role": item.get("role"),
                "kind": item.get("kind"),
                **dict(item.get("source") or {}),
            }
            for item in evidence_items
            if item.get("role") == "primary"
        ],
    }
    return result

