"""Workflow display metadata used by streaming services."""

from __future__ import annotations

from typing import Any


WORKFLOW_NODE_META: dict[str, dict[str, dict[str, Any]]] = {
    "agent": {
        "intake": {
            "label": "整理上下文",
            "progress_message": "正在整理请求上下文...",
        },
        "classify": {
            "label": "识别任务",
            "progress_message": "正在识别任务类型...",
        },
        "route": {
            "label": "选择路径",
            "progress_message": "正在选择处理路径...",
        },
        "orchestrate_plan": {
            "label": "规划执行",
            "progress_message": "正在规划执行步骤...",
        },
        "dispatch": {
            "label": "分发执行",
            "progress_message": "正在分发子智能体执行...",
        },
        "collect": {
            "label": "收集结果",
            "progress_message": "正在收集执行结果...",
        },
        "synthesize": {
            "label": "整编结果",
            "progress_message": "正在整编最终结果...",
        },
        "respond": {
            "label": "输出结果",
            "progress_message": "正在整理最终响应...",
        },
    },
    "knowledge_qa": {
        "plan_query": {
            "label": "规划查询",
            "progress_message": "正在规划知识库检索线索...",
        },
        "plan_retrieval": {
            "label": "规划检索",
            "progress_message": "正在规划知识库检索...",
        },
        "retrieve_knowledge": {
            "label": "检索知识",
            "progress_message": "正在检索知识库...",
        },
        "compose_result": {
            "label": "整理结果",
            "progress_message": "正在整理知识库结果...",
        },
    },
    "business_ops": {
        "analyze_request": {
            "label": "分析请求",
            "progress_message": "正在分析业务请求...",
        },
        "match_operation": {
            "label": "匹配操作",
            "progress_message": "正在匹配业务操作...",
        },
        "execute_operation": {
            "label": "执行业务操作",
            "progress_message": "正在查询业务数据...",
        },
        "replan_operation_params": {
            "label": "修正业务参数",
            "progress_message": "正在修正业务查询参数...",
        },
        "compose_result": {
            "label": "整理结果",
            "progress_message": "正在整理处理结果...",
        },
    },
}

OUTPUT_NODE_IDS = {"compose_result", "respond"}

CUSTOMER_STAGE_TITLES = {
    "understand": "理解需求",
    "plan": "规划步骤",
    "knowledge_search": "查阅资料",
    "business_query": "查询业务数据",
    "execute": "处理任务",
    "compose": "整理答案",
}

NODE_CUSTOMER_STAGES = {
    "agent": {
        "intake": "understand",
        "classify": "understand",
        "route": "understand",
        "orchestrate_plan": "plan",
        "dispatch": "execute",
        "collect": "execute",
        "synthesize": "compose",
        "respond": "compose",
    },
    "knowledge_qa": {
        "plan_query": "understand",
        "plan_retrieval": "knowledge_search",
        "retrieve_knowledge": "knowledge_search",
        "compose_result": "compose",
    },
    "business_ops": {
        "analyze_request": "understand",
        "match_operation": "business_query",
        "execute_operation": "business_query",
        "replan_operation_params": "business_query",
        "compose_result": "compose",
    },
}

LEGACY_CUSTOMER_STAGE_ALIASES = {
    "intake": "understand",
    "classify": "understand",
    "route": "understand",
    "orchestrate_plan": "plan",
    "dispatch": "execute",
    "collect": "execute",
    "synthesize": "compose",
    "understand": "understand",
    "execute": "execute",
    "compose": "compose",
}


def get_node_label(workflow_id: str, node_id: str) -> str:
    """Return the display label for a workflow node."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("label", node_id)


def get_node_model(workflow_id: str, node_id: str) -> str | None:
    """Return the display model name for a workflow node, if configured."""

    return WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("model")


def get_node_progress_message(workflow_id: str, node_id: str) -> str:
    """Return the user-facing progress message for a workflow node."""

    return (
        WORKFLOW_NODE_META.get(workflow_id, {}).get(node_id, {}).get("progress_message")
        or "正在处理..."
    )


def build_node_summary(workflow_id: str, node_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """Return an intentionally empty node payload for node_complete events."""

    _ = (workflow_id, node_id, state)
    return {}


def _customer_stage_from_payload(
    *,
    workflow_id: str,
    node_id: str,
    legacy_display_stage: str,
) -> str:
    if legacy_display_stage == "execute":
        if workflow_id == "knowledge_qa":
            return "knowledge_search"
        if workflow_id == "business_ops":
            return "business_query"

    if legacy_display_stage:
        return LEGACY_CUSTOMER_STAGE_ALIASES.get(legacy_display_stage, legacy_display_stage)

    return NODE_CUSTOMER_STAGES.get(workflow_id, {}).get(node_id, node_id)


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

    if node_id in OUTPUT_NODE_IDS and not legacy_display_stage:
        normalized_payload.pop("activity_text", None)
        normalized_payload.pop("activity_status", None)
        return normalized_payload

    customer_stage = _customer_stage_from_payload(
        workflow_id=workflow_id,
        node_id=node_id,
        legacy_display_stage=legacy_display_stage,
    )
    normalized_payload["display_stage"] = customer_stage
    normalized_payload["display_title"] = CUSTOMER_STAGE_TITLES.get(
        customer_stage,
        node_name or get_node_label(workflow_id, node_id),
    )
    return normalized_payload
