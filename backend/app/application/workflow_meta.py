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
    "business_ops": {
        "analyze_request": {"label": "分析请求"},
        "match_operation": {"label": "匹配操作"},
        "execute_operation": {"label": "执行业务操作"},
        "compose_result": {"label": "整理结果"},
    },
}

EXECUTE_STAGE_TITLES: dict[str, str] = {
    "knowledge_qa": "🔍 查阅相关资料",
    "business_ops": "📊 查询业务数据",
    "clarify": "🚀 补充必要信息",
    "direct_answer": "🚀 处理请求",
}


def get_node_workflow_id(root_workflow_id: str, node_id: str) -> str:
    """Resolve the real workflow owner for a streamed node."""

    if node_id in WORKFLOW_NODE_META.get("knowledge_qa", {}):
        return "knowledge_qa"
    if node_id in WORKFLOW_NODE_META.get("business_ops", {}):
        return "business_ops"
    if node_id in WORKFLOW_NODE_META.get(root_workflow_id, {}):
        return root_workflow_id
    return root_workflow_id


def get_node_label(workflow_id: str, node_id: str) -> str:
    """Return the display label for a workflow node."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("label", node_id)


def get_node_model(workflow_id: str, node_id: str) -> str | None:
    """Return the display model name for a workflow node, if configured."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("model")


def get_display_stage_plan(target_id: str | None) -> list[dict[str, str]]:
    """Return the stable user-facing stage plan for one assistant turn."""

    normalized = str(target_id or "").strip()
    return [
        {"id": "understand", "title": "🤔 思考您的问题"},
        {
            "id": "execute",
            "title": EXECUTE_STAGE_TITLES.get(normalized, EXECUTE_STAGE_TITLES["direct_answer"]),
        },
        {"id": "compose", "title": "💡 总结最终结果"},
    ]
