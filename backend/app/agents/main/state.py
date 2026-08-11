"""State contract for the top-level Agent workflow."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


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


class AgentIntent(TypedDict):
    goal: str


class AgentRouting(TypedDict):
    route_type: str
    intent: AgentIntent
    target_sub_agents: list[str]
    clarification_question: NotRequired[str | None]
    reason: str


class AgentTaskStep(TypedDict):
    task_id: str
    sub_agent_id: str
    goal: str
    depends_on: list[str]


class AgentTaskPlan(TypedDict):
    execution_mode: Literal["none", "single", "parallel", "dag"]
    steps: list[AgentTaskStep]
    reason: str


class AgentExecution(TypedDict, total=False):
    task_id: str
    sub_agent_id: str
    status: str
    sub_agent_result: dict[str, Any]
    dependency_results: dict[str, dict[str, Any]]
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
    """Minimal graph state. Each phase owns exactly one top-level field."""

    input: AgentInput
    routing: NotRequired[AgentRouting]
    plan: NotRequired[AgentTaskPlan]
    executions: NotRequired[dict[str, AgentExecution]]
    result: NotRequired[AgentResult]
    response: NotRequired[AgentResponse]
