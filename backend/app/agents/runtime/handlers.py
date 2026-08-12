"""Executable handler registry and workflow input adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

HandlerInputBuilder = Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class HandlerDefinition:
    """Executable handler contract exposed to task routing."""

    handler_id: str
    workflow_id: str
    description: str
    handoff_action: str | None
    input_builder: HandlerInputBuilder


def _build_shared_input(
    state: Mapping[str, Any],
    step: Mapping[str, Any],
    *,
    workflow_id: str,
) -> dict[str, Any]:
    agent_input = dict(state.get("input") or {})
    intent = dict(state.get("understanding") or {})
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


HANDLER_DEFINITIONS: tuple[HandlerDefinition, ...] = (
    HandlerDefinition(
        handler_id="knowledge_qa",
        workflow_id="knowledge_qa",
        description=(
            "检索当前应用绑定知识库中的版本化企业知识；"
            "用于回答功能是否支持、页面入口、操作步骤、筛选排序条件、字段含义、配置项和业务规则等静态资料问题；"
            "不执行系统修改，也不要求外部实时数据"
        ),
        handoff_action="结合相关资料看一下具体情况",
        input_builder=build_knowledge_qa_input,
    ),
    HandlerDefinition(
        handler_id="business_ops",
        workflow_id="business_ops",
        description=(
            "调用当前应用端已授权的只读外部业务工具；"
            "用于返回当前具体记录、名单、数量、统计值或实时状态等动态业务数据；"
            "不承接单纯的功能说明、操作步骤或配置规则问题"
        ),
        handoff_action="调用当前应用端的业务工具看一下具体情况",
        input_builder=build_business_ops_input,
    ),
)


def get_handler_definitions() -> tuple[HandlerDefinition, ...]:
    """Return handlers visible to top-level task routing."""

    return HANDLER_DEFINITIONS


def get_handler_definition(handler_id: str) -> HandlerDefinition:
    """Return one registered handler definition."""

    for definition in HANDLER_DEFINITIONS:
        if definition.handler_id == handler_id:
            return definition
    raise KeyError(f"Unknown handler id: {handler_id}")
