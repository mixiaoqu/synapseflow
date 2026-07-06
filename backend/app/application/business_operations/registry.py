"""Dynamic registry for project-app business operations."""

from __future__ import annotations

from app.application.business_operations.schemas import (
    BusinessOperationDefinition,
    BusinessOperationParamSpec,
)
from app.repositories.business_tool_repository import BusinessToolExecutionRecord


class BusinessOperationRegistry:
    """Build operation definitions from published tools available to one app."""

    @staticmethod
    def from_tool_record(record: BusinessToolExecutionRecord) -> BusinessOperationDefinition:
        tool = record.tool
        return BusinessOperationDefinition(
            id=tool.tool_key,
            name=tool.name,
            description=tool.description or tool.name,
            risk_level=tool.risk_level,
            requires_confirmation=tool.requires_confirmation,
            params=[
                BusinessOperationParamSpec(
                    key=str(item.get("key") or "").strip(),
                    label=str(item.get("label") or item.get("key") or "参数").strip(),
                    type=str(item.get("type") or "text").strip(),
                    required=bool(item.get("required")),
                    description=str(item.get("description") or "").strip(),
                )
                for item in list(tool.params_schema or [])
                if str(item.get("key") or "").strip()
            ],
        )

    def list_from_records(
        self,
        records: list[BusinessToolExecutionRecord],
    ) -> list[BusinessOperationDefinition]:
        return [self.from_tool_record(record) for record in records]
