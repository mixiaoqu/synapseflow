"""Top-level sub-agent metadata and child-graph input adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

SubAgentInputBuilder = Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class SubAgentDefinition:
    """Public sub-agent contract exposed to the main agent."""

    sub_agent_id: str
    graph_id: str
    description: str
    handoff_action: str | None
    input_builder: SubAgentInputBuilder


def _build_shared_input(
    state: Mapping[str, Any],
    step: Mapping[str, Any],
    *,
    workflow_id: str,
) -> dict[str, Any]:
    classification = dict(state.get("classification") or {})
    intent = dict(classification.get("intent") or {})
    step_goal = str(step.get("goal") or "").strip()
    goal = step_goal or str(intent.get("goal") or "").strip()
    original_query = str(state.get("normalized_query") or state.get("query") or "").strip()
    metadata = dict(state.get("metadata") or {})
    metadata["workflow"] = workflow_id
    metadata["parent_step_id"] = step.get("step_id")
    dependency_results = {
        str(step_id): dict(result)
        for step_id, result in dict(step.get("dependency_results") or {}).items()
        if isinstance(result, Mapping)
    }
    metadata["dependency_step_ids"] = list(dependency_results)
    return {
        "workflow_id": workflow_id,
        "request_id": state.get("request_id"),
        "run_id": state.get("run_id"),
        "session_id": state.get("session_id"),
        "metadata": metadata,
        "messages": list(state.get("messages") or []),
        "chat_history": list(state.get("chat_history") or []),
        "memory_summary": state.get("memory_summary"),
        "runtime_context": dict(state.get("runtime_context") or {}),
        "user_id": state.get("user_id"),
        "team_id": state.get("team_id"),
        "original_query": original_query,
        "query": goal or original_query,
        "intent": intent,
        "dependency_results": dependency_results,
    }


def build_knowledge_qa_input(
    state: Mapping[str, Any],
    step: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the field-limited input accepted by knowledge_qa."""

    child_input = _build_shared_input(state, step, workflow_id="knowledge_qa")
    knowledge_base_id = state.get("knowledge_base_id")
    if knowledge_base_id is None:
        knowledge_base_ids = list(state.get("knowledge_base_ids") or [])
        knowledge_base_id = knowledge_base_ids[0] if knowledge_base_ids else None
    child_input.update(
        {
            "knowledge_base_id": knowledge_base_id,
            "category_id": state.get("category_id"),
            "page_context": dict(state.get("page_context") or {}),
            "allowed_document_statuses": list(state.get("allowed_document_statuses") or []),
        }
    )
    return child_input


def build_business_ops_input(
    state: Mapping[str, Any],
    step: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the field-limited input accepted by business_ops."""

    child_input = _build_shared_input(state, step, workflow_id="business_ops")
    child_input.update(
        {
            "product_id": state.get("product_id"),
            "project_id": state.get("project_id"),
            "project_app_id": state.get("project_app_id"),
            "external_user_id": state.get("external_user_id"),
            "external_user_name": state.get("external_user_name"),
            "store_id": state.get("store_id"),
            "trusted_scope": dict(state.get("trusted_scope") or {}),
            "page_context": dict(state.get("page_context") or {}),
            "page_config": dict(state.get("page_config") or {}),
        }
    )
    return child_input


SUB_AGENT_DEFINITIONS: tuple[SubAgentDefinition, ...] = (
    SubAgentDefinition(
        sub_agent_id="knowledge_qa",
        graph_id="knowledge_qa",
        description="查询知识库中的规则、说明、流程和文档内容",
        handoff_action="结合相关资料看一下具体情况",
        input_builder=build_knowledge_qa_input,
    ),
    SubAgentDefinition(
        sub_agent_id="business_ops",
        graph_id="business_ops",
        description="调用当前应用端已授权的外部业务工具，查询或处理实时业务数据",
        handoff_action="调用当前应用端的业务工具看一下具体情况",
        input_builder=build_business_ops_input,
    ),
)


def get_sub_agent_definitions() -> tuple[SubAgentDefinition, ...]:
    """Return sub-agents visible to the top-level orchestration graph."""

    return SUB_AGENT_DEFINITIONS


def get_sub_agent_definition(sub_agent_id: str) -> SubAgentDefinition:
    """Return one registered sub-agent definition."""

    for definition in SUB_AGENT_DEFINITIONS:
        if definition.sub_agent_id == sub_agent_id:
            return definition
    raise KeyError(f"Unknown sub-agent id: {sub_agent_id}")
