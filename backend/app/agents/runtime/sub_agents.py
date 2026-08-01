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
    agent_input = dict(state.get("input") or {})
    routing = dict(state.get("routing") or {})
    intent = dict(routing.get("intent") or {})
    step_goal = str(step.get("goal") or "").strip()
    goal = step_goal or str(intent.get("goal") or "").strip()
    intent["goal"] = goal
    original_query = str(agent_input.get("query") or "").strip()
    metadata = dict(agent_input.get("metadata") or {})
    metadata["workflow"] = workflow_id
    metadata["parent_task_id"] = step.get("task_id")
    dependency_results = {
        str(step_id): dict(result)
        for step_id, result in dict(step.get("dependency_results") or {}).items()
        if isinstance(result, Mapping)
    }
    metadata["dependency_step_ids"] = list(dependency_results)
    return {
        "workflow_id": workflow_id,
        "request_id": agent_input.get("request_id"),
        "run_id": agent_input.get("run_id"),
        "session_id": dict(agent_input.get("conversation") or {}).get("session_id"),
        "metadata": metadata,
        "messages": list(dict(agent_input.get("conversation") or {}).get("history") or []),
        "chat_history": list(dict(agent_input.get("conversation") or {}).get("history") or []),
        "memory_summary": dict(agent_input.get("conversation") or {}).get("summary"),
        "runtime_context": dict(agent_input.get("runtime_context") or {}),
        "user_id": dict(agent_input.get("identity") or {}).get("user_id"),
        "team_id": dict(agent_input.get("identity") or {}).get("team_id"),
        "original_query": original_query,
        "query": goal or original_query,
        "intent": intent,
        "expected_facts": [
            str(item).strip()
            for item in list(step.get("expected_facts") or [])
            if str(item).strip()
        ],
        "dependency_results": dependency_results,
    }


def build_knowledge_qa_input(
    state: Mapping[str, Any],
    step: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the field-limited input accepted by knowledge_qa."""

    child_input = _build_shared_input(state, step, workflow_id="knowledge_qa")
    agent_input = dict(state.get("input") or {})
    resources = dict(agent_input.get("resources") or {})
    knowledge_base_id = resources.get("knowledge_base_id")
    child_input.update(
        {
            "knowledge_base_id": knowledge_base_id,
            "category_id": resources.get("category_id"),
            "page_context": dict(agent_input.get("page_context") or {}),
            "allowed_document_statuses": list(resources.get("allowed_document_statuses") or []),
        }
    )
    return child_input


def build_business_ops_input(
    state: Mapping[str, Any],
    step: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the field-limited input accepted by business_ops."""

    child_input = _build_shared_input(state, step, workflow_id="business_ops")
    agent_input = dict(state.get("input") or {})
    resources = dict(agent_input.get("resources") or {})
    identity = dict(agent_input.get("identity") or {})
    child_input.update(
        {
            "product_id": resources.get("product_id"),
            "project_id": resources.get("project_id"),
            "project_app_id": resources.get("project_app_id"),
            "external_user_id": identity.get("external_user_id"),
            "external_user_name": identity.get("external_user_name"),
            "store_id": resources.get("store_id"),
            "trusted_scope": dict(resources.get("trusted_scope") or {}),
            "page_context": dict(agent_input.get("page_context") or {}),
            "page_config": dict(agent_input.get("page_config") or {}),
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
