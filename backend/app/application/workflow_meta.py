"""Workflow display metadata used by streaming services."""

from __future__ import annotations

from typing import Any

WORKFLOW_NODE_META: dict[str, dict[str, dict[str, Any]]] = {
    "agent": {
        "load_context": {"label": "加载上下文"},
        "understand": {"label": "理解意图"},
        "route": {"label": "匹配能力"},
        "clarify": {"label": "请求澄清"},
        "plan": {"label": "制定计划"},
        "execute": {"label": "执行计划"},
        "respond": {"label": "输出结果"},
    },
    "knowledge_qa": {
        "analyze_question": {"label": "分析问题"},
        "plan_retrieval": {"label": "规划检索"},
        "retrieve_knowledge": {"label": "检索知识"},
        "compose_answer": {"label": "组织回答"},
    },
}


def get_node_workflow_id(root_workflow_id: str, node_id: str) -> str:
    """Resolve the real workflow owner for a streamed node."""

    if node_id in WORKFLOW_NODE_META.get("knowledge_qa", {}):
        return "knowledge_qa"
    if node_id in WORKFLOW_NODE_META.get(root_workflow_id, {}):
        return root_workflow_id
    return root_workflow_id


def get_node_label(workflow_id: str, node_id: str) -> str:
    """Return the display label for a workflow node."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("label", node_id)


def get_node_model(workflow_id: str, node_id: str) -> str | None:
    """Return the display model name for a workflow node, if configured."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("model")
