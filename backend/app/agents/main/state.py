"""State contract for the top-level Agent workflow."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage


class AgentAssistantContext(TypedDict, total=False):
    id: int
    name: str
    model_key: str
    persona_prompt: str
    rule_template: str


class AgentIdentity(TypedDict, total=False):
    user_id: int
    team_id: int
    external_user_id: str
    external_user_name: str


class AgentResourceScope(TypedDict, total=False):
    product_id: int
    project_id: int
    project_app_id: int
    knowledge_base_id: int
    category_id: int
    store_id: str
    trusted_scope: dict[str, Any]
    allowed_document_statuses: list[str]


class AgentConversationContext(TypedDict, total=False):
    session_id: str
    history: list[dict[str, Any]]
    summary: str


class AgentInput(TypedDict):
    """Trusted, fully prepared input accepted by the graph."""

    request_id: str
    run_id: str
    query: str
    identity: AgentIdentity
    resources: AgentResourceScope
    conversation: AgentConversationContext
    assistant: AgentAssistantContext
    page_context: dict[str, Any]
    page_config: dict[str, Any]
    runtime_context: dict[str, Any]
    metadata: dict[str, Any]
    tool_context: NotRequired[dict[str, Any]]


class AgentDecision(TypedDict):
    goal: str
    status: Literal["answered", "partial", "clarification_needed", "out_of_scope", "failed"]
    message: str


class AgentExecution(TypedDict, total=False):
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    goal: str
    handler_id: str | None
    status: str
    task_result: dict[str, Any]
    result_ids: list[str]
    reused_from: str
    diagnostics: dict[str, Any]
    error: str


class AgentResult(TypedDict):
    status: str
    answer_status: str
    knowledge_context: list[dict[str, Any]]
    business_data: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    clarifications: list[dict[str, Any]]
    answer_material: dict[str, Any]
    success_count: NotRequired[int]
    failed_count: NotRequired[int]
    needs_input_count: NotRequired[int]
    partial: NotRequired[bool]
    citation_refs: NotRequired[list[str]]
    normalized_query: NotRequired[str]
    retrieval_profile: NotRequired[str]
    route_reason: NotRequired[str]
    retrieval_execution_plan: NotRequired[dict[str, Any]]
    semantic_queries: NotRequired[list[str]]
    lexical_terms: NotRequired[list[str]]
    query_plan_trace: NotRequired[dict[str, Any]]
    retrieval_status: NotRequired[str]
    retrieval_reason_code: NotRequired[str]
    retrieval_budget: NotRequired[dict[str, Any]]
    retrieval_metrics: NotRequired[dict[str, Any]]
    retrieval_warnings: NotRequired[list[str]]


class AgentResponse(TypedDict):
    answer: str
    status: str
    sources: list[dict[str, Any]]


class AgentState(TypedDict):
    """本轮对话的决策消息、能力调用及可追溯结果。"""

    input: AgentInput
    messages: NotRequired[list[BaseMessage]]
    decision: NotRequired[AgentDecision]
    plan: NotRequired[str]
    pending_calls: NotRequired[list[dict[str, Any]]]
    decision_count: NotRequired[int]
    operation_count: NotRequired[int]
    deadline: NotRequired[float]
    executions: NotRequired[dict[str, AgentExecution]]
    result: NotRequired[AgentResult]
    response: NotRequired[AgentResponse]
