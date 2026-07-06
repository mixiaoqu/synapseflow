"""Top-level capability metadata and child-graph input adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

CapabilityInputBuilder = Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class CapabilityDefinition:
    """Public capability contract exposed to the top-level agent."""

    capability_id: str
    graph_id: str
    description: str
    handoff_action: str | None
    input_builder: CapabilityInputBuilder


def _build_shared_input(
    state: Mapping[str, Any],
    decision: Mapping[str, Any],
    *,
    workflow_id: str,
) -> dict[str, Any]:
    intent = dict(decision.get("intent") or {})
    goal = str(intent.get("goal") or "").strip()
    original_query = str(state.get("query") or "").strip()
    metadata = dict(state.get("metadata") or {})
    metadata["workflow"] = workflow_id
    return {
        "workflow_id": workflow_id,
        "request_id": state.get("request_id"),
        "run_id": state.get("run_id"),
        "session_id": state.get("session_id"),
        "metadata": metadata,
        "messages": list(state.get("messages") or []),
        "chat_history": list(state.get("chat_history") or []),
        "memory_summary": state.get("memory_summary"),
        "user_id": state.get("user_id"),
        "team_id": state.get("team_id"),
        "original_query": original_query,
        "query": goal or original_query,
        "intent": intent,
    }


def build_knowledge_qa_input(
    state: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the field-limited input accepted by knowledge_qa."""

    child_input = _build_shared_input(state, decision, workflow_id="knowledge_qa")
    knowledge_base_id = state.get("knowledge_base_id")
    if knowledge_base_id is None:
        knowledge_base_ids = list(state.get("knowledge_base_ids") or [])
        knowledge_base_id = knowledge_base_ids[0] if knowledge_base_ids else None
    child_input.update(
        {
            "knowledge_base_id": knowledge_base_id,
            "category_id": state.get("category_id"),
            "page_context": dict(state.get("page_context") or {}),
            "allowed_document_statuses": list(
                state.get("allowed_document_statuses") or []
            ),
        }
    )
    return child_input


def build_business_ops_input(
    state: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the field-limited input accepted by business_ops."""

    child_input = _build_shared_input(state, decision, workflow_id="business_ops")
    child_input.update(
        {
            "product_id": state.get("product_id"),
            "project_id": state.get("project_id"),
            "project_app_id": state.get("project_app_id"),
            "external_user_id": state.get("external_user_id"),
            "external_user_name": state.get("external_user_name"),
            "store_id": state.get("store_id"),
            "page_context": dict(state.get("page_context") or {}),
            "page_config": dict(state.get("page_config") or {}),
        }
    )
    return child_input


CAPABILITY_DEFINITIONS: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        capability_id="knowledge_qa",
        graph_id="knowledge_qa",
        description="查询知识库中的规则、说明、流程和文档内容",
        handoff_action="结合相关资料看一下具体情况",
        input_builder=build_knowledge_qa_input,
    ),
    CapabilityDefinition(
        capability_id="business_ops",
        graph_id="business_ops",
        description="调用当前应用端已授权的外部业务工具，查询或处理实时业务数据",
        handoff_action="调用当前应用端的业务工具看一下具体情况",
        input_builder=build_business_ops_input,
    ),
)


def get_capability_definitions() -> tuple[CapabilityDefinition, ...]:
    """Return capabilities visible to the top-level decision node."""

    return CAPABILITY_DEFINITIONS


def get_capability_definition(capability_id: str) -> CapabilityDefinition:
    """Return one registered capability definition."""

    for definition in CAPABILITY_DEFINITIONS:
        if definition.capability_id == capability_id:
            return definition
    raise KeyError(f"Unknown capability id: {capability_id}")
