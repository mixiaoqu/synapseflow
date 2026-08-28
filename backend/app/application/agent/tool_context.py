"""从现有授权目录准备主 Agent 可见的业务能力摘要。"""

from typing import Any

from app.agents.main.state import AgentInput
from app.application.business_operations import BusinessOperationService


async def prepare_tool_context(agent_input: AgentInput) -> dict[str, Any]:
    app_id = agent_input["resources"].get("project_app_id")
    operations = await BusinessOperationService().list_available_operations(app_id)
    return {
        "business_tools": [
            {
                "name": operation.name,
                "description": operation.description,
                "required_inputs": [
                    {"name": param.key, "description": param.description}
                    for param in operation.params
                    if param.required
                ],
            }
            for operation in operations
            if operation.read_only
        ]
    }
