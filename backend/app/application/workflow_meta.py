"""Workflow display metadata used by streaming services."""

from __future__ import annotations

from typing import Any

WORKFLOW_NODE_META: dict[str, dict[str, dict[str, Any]]] = {
    "agent": {
        "decide": {"label": "理解问题"},
        "clarify": {"label": "请求澄清"},
        "invoke": {"label": "调用能力"},
        "respond": {"label": "输出结果"},
    },
    "knowledge_qa": {
        "analyze_question": {"label": "分析问题"},
        "plan_retrieval": {"label": "规划检索"},
        "retrieve_knowledge": {"label": "检索知识"},
        "compose_answer": {"label": "组织回答"},
    },
    "business_ops": {
        "analyze_request": {"label": "分析请求"},
        "match_operation": {"label": "匹配操作"},
        "execute_operation": {"label": "执行业务操作"},
        "compose_result": {"label": "整理结果"},
    },
}

OUTPUT_NODE_IDS = {"compose_answer", "compose_result", "respond"}


def get_node_label(workflow_id: str, node_id: str) -> str:
    """Return the display label for a workflow node."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("label", node_id)


def get_node_model(workflow_id: str, node_id: str) -> str | None:
    """Return the display model name for a workflow node, if configured."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("model")


def normalize_activity_payload(
    *,
    workflow_id: str,
    node_id: str,
    node_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Expose only real runtime child-node activity for display."""

    normalized_payload = dict(payload)
    legacy_display_stage = str(normalized_payload.get("display_stage") or "").strip()
    for key in ("display_stage", "display_title"):
        normalized_payload.pop(key, None)

    if node_id in OUTPUT_NODE_IDS or legacy_display_stage == "compose":
        normalized_payload.pop("activity_text", None)
        normalized_payload.pop("activity_status", None)
        return normalized_payload

    normalized_payload["display_stage"] = node_id
    normalized_payload["display_title"] = node_name or get_node_label(workflow_id, node_id)
    return normalized_payload
