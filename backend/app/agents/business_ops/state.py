"""State contract for the business operations workflow."""

from typing import Any, Dict, Optional

from app.agents.runtime.context import BaseAgentContext


class BusinessOpsState(BaseAgentContext, total=False):
    """Workflow state for business_ops."""

    workflow_id: str
    session_id: Optional[str]
    original_query: str
    query: str
    intent: Dict[str, Any]
    dependency_results: Dict[str, Dict[str, Any]]
    product_id: Optional[int]
    project_id: Optional[int]
    project_app_id: Optional[int]
    external_user_id: Optional[str]
    external_user_name: Optional[str]
    store_id: Optional[str]
    trusted_scope: Dict[str, Any]
    page_context: Dict[str, Any]
    page_config: Dict[str, Any]

    business_request: Dict[str, Any]
    available_business_tools: list[Dict[str, Any]]
    business_operation: Dict[str, Any]
    business_operation_result: Dict[str, Any]
    business_result: Dict[str, Any]
    business_retry_count: int
    business_retry_error: Dict[str, Any]
    business_call_count: int
    business_call_history: list[Dict[str, Any]]
    sub_agent_result: Dict[str, Any]

    answer: str
    answer_status: str
