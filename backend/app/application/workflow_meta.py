"""Workflow display metadata used by streaming services."""

from __future__ import annotations

from typing import Any

WORKFLOW_NODE_META: dict[str, dict[str, dict[str, Any]]] = {
    "kb_chat": {
        "plan_query": {"label": "正在理解你的问题"},
        "rewrite_query": {"label": "正在整理检索线索"},
        "retrieve": {"label": "正在查找知识库内容"},
        "answer": {"label": "正在组织最终回答"},
    },
    "kb_chat_v2": {
        "analyze": {"label": "正在分析问题并生成检索方案"},
        "rewrite_query": {"label": "正在整理检索线索"},
        "retrieve": {"label": "正在查找知识库内容"},
        "evaluate": {"label": "正在核对答案依据"},
        "answer": {"label": "正在组织最终回答"},
    },
}


def get_node_label(workflow_id: str, node_id: str) -> str:
    """Return the display label for a workflow node."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("label", node_id)


def get_node_model(workflow_id: str, node_id: str) -> str | None:
    """Return the display model name for a workflow node, if configured."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("model")
