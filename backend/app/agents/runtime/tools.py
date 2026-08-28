"""内置能力工具契约与子图输入适配。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from langchain_core.utils.function_calling import convert_to_openai_function
from pydantic import BaseModel, ConfigDict, Field

from app.services.web_search import is_web_search_available

ToolInputBuilder = Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    goal: str = Field(
        min_length=1, max_length=2000, description="本次调用要完成的具体目标，保留对象、条件与约束"
    )
    context: str = Field(default="", max_length=4000, description="与本次目标相关的已有材料和条件")
    result_ids: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="需要引用的工具消息顶层 result_id；运行时注入对应原始结果",
    )


@dataclass(frozen=True)
class AgentToolDefinition:
    """工具定义是能力描述、参数与适配关系的唯一来源。"""

    name: str
    workflow_id: str
    description: str
    input_builder: ToolInputBuilder
    available: Callable[[Mapping[str, Any]], bool]
    describe_context: Callable[[Mapping[str, Any]], str] = lambda _: ""

    def schema(self, agent_input: Mapping[str, Any]) -> dict[str, Any]:
        function = convert_to_openai_function(ToolArguments, strict=True)
        function["name"] = self.name
        function["description"] = self.description + self.describe_context(agent_input)
        return {
            "type": "function",
            "function": function,
        }


def _build_shared_input(
    state: Mapping[str, Any],
    step: Mapping[str, Any],
    *,
    workflow_id: str,
) -> dict[str, Any]:
    agent_input = dict(state.get("input") or {})
    goal = str(step["goal"])
    original_query = str(agent_input.get("query") or "").strip()
    metadata = dict(agent_input.get("metadata") or {})
    metadata["workflow"] = workflow_id
    metadata["parent_task_id"] = step["call_id"]
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
        "intent": {"goal": goal},
        "task_context": str(step.get("context") or ""),
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


def build_web_search_input(
    state: Mapping[str, Any],
    step: Mapping[str, Any],
) -> dict[str, Any]:
    """仅传递公开目标；不自动携带对话、身份、页面或依赖结果。"""
    agent_input = dict(state.get("input") or {})
    return {
        "workflow_id": "web_search",
        "run_id": agent_input.get("run_id"),
        "metadata": {"parent_task_id": step["call_id"]},
        "query": str(step["goal"]).strip(),
    }


def _business_tools(agent_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    return list(dict(agent_input.get("tool_context") or {}).get("business_tools") or [])


def _business_description(agent_input: Mapping[str, Any]) -> str:
    import json

    return "\n当前应用实际可用的查询能力：\n" + json.dumps(
        _business_tools(agent_input), ensure_ascii=False, default=str
    )


TOOL_DEFINITIONS: tuple[AgentToolDefinition, ...] = (
    AgentToolDefinition(
        name="search_web",
        workflow_id="web_search",
        description=(
            "搜索公开互联网并提取网页正文节选，返回 URL、标题、抓取时间和证据状态；"
            "用于外部公开知识及需要查证的信息。goal 必须是最多 500 字的独立公开搜索词；"
            "仅包含检索主题与必要公开限定词，不含用户身份、联系方式、凭据或内部业务记录；"
            "context 和 result_ids 留空，不向外部传递私有材料。"
            "网页内容是未经平台审核的外部资料；搜索摘要只作线索，不能单凭摘要确认高风险事实。"
        ),
        input_builder=build_web_search_input,
        available=lambda _: is_web_search_available(),
    ),
    AgentToolDefinition(
        name="search_knowledge",
        workflow_id="knowledge_qa",
        description=(
            "检索当前应用绑定知识库中的版本化企业知识；"
            "用于回答功能是否支持、页面入口、操作步骤、筛选排序条件、字段含义、配置项和业务规则等静态资料问题；"
            "返回可追溯的资料证据、来源和检索状态"
        ),
        input_builder=build_knowledge_qa_input,
        available=lambda agent_input: bool(
            dict(agent_input.get("resources") or {}).get("knowledge_base_id")
        ),
    ),
    AgentToolDefinition(
        name="query_business_data",
        workflow_id="business_ops",
        description=(
            "调用当前应用端已授权的只读外部业务工具；"
            "用于返回当前具体记录、名单、数量、统计值或实时状态等动态业务数据；"
            "返回结构化结果、实际查询条件及执行状态"
        ),
        input_builder=build_business_ops_input,
        available=lambda agent_input: bool(_business_tools(agent_input)),
        describe_context=_business_description,
    ),
)


def get_tool_definitions() -> tuple[AgentToolDefinition, ...]:
    return TOOL_DEFINITIONS
