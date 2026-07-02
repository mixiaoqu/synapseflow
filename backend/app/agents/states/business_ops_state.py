"""State model for the business operations workflow."""

from typing import Any, Dict, List, Optional

from app.agents.runtime.context import BaseAgentContext


class BusinessOpsState(BaseAgentContext, total=False):
    """Workflow state for business_ops."""

    workflow_id: str
    session_id: Optional[str]
    query: str
    product_id: Optional[int]
    project_id: Optional[int]
    project_app_id: Optional[int]
    external_user_id: Optional[str]
    external_user_name: Optional[str]
    store_id: Optional[str]
    page_context: Dict[str, Any]
    page_config: Dict[str, Any]
    chat_history: List[Dict[str, Any]]
    memory_summary: Optional[str]

    business_request: Dict[str, Any]
    business_operation: Dict[str, Any]
    business_operation_result: Dict[str, Any]
    business_result: Dict[str, Any]

    answer: str
    answer_status: str
