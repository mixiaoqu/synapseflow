"""State model for the top-level agent workflow."""

from typing import Any, Dict, List, Optional

from app.agents.runtime.context import BaseAgentContext


class AgentState(BaseAgentContext, total=False):
    """Workflow state for agent."""

    session_id: Optional[str]
    query: str
    product_id: Optional[int]
    project_id: Optional[int]
    project_app_id: Optional[int]
    external_user_id: Optional[str]
    external_user_name: Optional[str]
    store_id: Optional[str]
    assistant_id: Optional[int]
    assistant_name: Optional[str]
    assistant_welcome_message: Optional[str]
    assistant_placeholder_text: Optional[str]
    assistant_llm_model_key: Optional[str]
    assistant_persona_prompt: Optional[str]
    assistant_rule_template: Optional[str]
    assistant_suggested_prompts: List[str]
    page_context: Dict[str, Any]
    page_config: Dict[str, Any]
    knowledge_base_ids: List[int]
    chat_history: List[Dict[str, Any]]
    memory_summary: Optional[str]
    allowed_document_statuses: List[str]

    normalized_query: str
    scope: Dict[str, Any]
    session_context: Dict[str, Any]
    channel_context: Dict[str, Any]
    trace: Dict[str, Any]
    classification: Dict[str, Any]
    route: Dict[str, Any]
    task_plan: Dict[str, Any]
    execution_runs: List[Dict[str, Any]]
    sub_agent_results: List[Dict[str, Any]]
    collected_results: Dict[str, Any]
    synthesized_result: Dict[str, Any]
    workflow_result: Dict[str, Any]
    response: Dict[str, Any]

    answer: str
    answer_status: str
    retrieved_docs: List[Dict[str, Any]]
    backend_citations: List[Dict[str, Any]]
    final_response: Dict[str, Any]
