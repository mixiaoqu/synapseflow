"""Dynamic registry for project-app Agent operations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.application.business_operations.schemas import (
    BusinessOperationDefinition,
    BusinessOperationParamSpec,
)
from app.repositories.agent_tool_repository import AgentToolExecutionRecord

AGENT_CONTEXT_PARAM_KEYS = {
    "admin_id",
    "admin_name",
    "external_user_id",
    "external_user_name",
    "page_type",
    "product_id",
    "project_app_id",
    "project_id",
    "request_id",
    "session_id",
    "store_id",
    "user_id",
}


class BusinessOperationRegistry:
    """Build operation definitions from published Agent tools available to one app."""

    @staticmethod
    def _filter_input_schema(params_schema: Any) -> dict[str, Any]:
        if isinstance(params_schema, dict):
            schema = deepcopy(params_schema)
            properties = schema.get("properties")
            if isinstance(properties, dict):
                schema["properties"] = {
                    str(key): spec
                    for key, spec in properties.items()
                    if str(key) not in AGENT_CONTEXT_PARAM_KEYS
                }
                required = schema.get("required")
                if isinstance(required, list):
                    schema["required"] = [
                        str(key)
                        for key in required
                        if str(key) in schema["properties"]
                    ]
            return schema
        if isinstance(params_schema, list):
            properties: dict[str, Any] = {}
            required: list[str] = []
            for item in params_schema:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key") or "").strip()
                if not key or key in AGENT_CONTEXT_PARAM_KEYS:
                    continue
                param_type = str(item.get("type") or "string").strip()
                properties[key] = {
                    "type": "string" if param_type in {"text", "select"} else param_type,
                    "title": str(item.get("label") or key).strip(),
                    "description": str(item.get("description") or "").strip(),
                }
                enum_values = item.get("enum") or item.get("options")
                if isinstance(enum_values, list):
                    properties[key]["enum"] = deepcopy(enum_values)
                if bool(item.get("required")):
                    required.append(key)
            return {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        return {"type": "object", "properties": {}, "required": []}

    @staticmethod
    def _params_from_schema(params_schema: Any) -> list[BusinessOperationParamSpec]:
        if isinstance(params_schema, dict):
            properties = params_schema.get("properties") if isinstance(params_schema.get("properties"), dict) else {}
            required = set(params_schema.get("required") or []) if isinstance(params_schema.get("required"), list) else set()
            params: list[BusinessOperationParamSpec] = []
            for key, spec in properties.items():
                if str(key) in AGENT_CONTEXT_PARAM_KEYS:
                    continue
                if not isinstance(spec, dict):
                    spec = {}
                schema_type = str(spec.get("type") or "text")
                param_type = "text" if schema_type == "string" else schema_type
                if schema_type in {"integer", "number"}:
                    param_type = "number"
                if isinstance(spec.get("enum"), list):
                    param_type = "select"
                if param_type not in {"text", "select", "number", "boolean", "array", "object"}:
                    param_type = "text"
                params.append(
                    BusinessOperationParamSpec(
                        key=str(key),
                        label=str(spec.get("title") or key),
                        type=param_type,
                        required=str(key) in required,
                        description=str(spec.get("description") or ""),
                        enum_values=list(spec.get("enum") or []),
                        default=spec.get("default"),
                    )
                )
            return params
        if isinstance(params_schema, list):
            return [
                BusinessOperationParamSpec(
                    key=str(item.get("key") or "").strip(),
                    label=str(item.get("label") or item.get("key") or "参数").strip(),
                    type=str(item.get("type") or "text").strip(),
                    required=bool(item.get("required")),
                    description=str(item.get("description") or "").strip(),
                    enum_values=list(item.get("enum") or item.get("options") or []),
                    default=item.get("default"),
                )
                for item in params_schema
                if (
                    isinstance(item, dict)
                    and str(item.get("key") or "").strip()
                    and str(item.get("key") or "").strip() not in AGENT_CONTEXT_PARAM_KEYS
                )
            ]
        return []

    @classmethod
    def from_tool_record(cls, record: AgentToolExecutionRecord) -> BusinessOperationDefinition:
        tool = record.tool
        input_schema = cls._filter_input_schema(tool.input_schema or {})
        return BusinessOperationDefinition(
            id=tool.tool_key,
            name=tool.name,
            description=tool.agent_description or tool.external_description or tool.name,
            domain=tool.domain or "general",
            action=tool.action or "execute",
            read_only=bool(tool.read_only),
            required_permissions=list(tool.required_permissions or []),
            risk_level=tool.risk_level,
            requires_confirmation=tool.requires_confirmation,
            required_scope=list(tool.required_context or []),
            params=cls._params_from_schema(input_schema),
            input_schema=input_schema,
        )

    def list_from_records(self, records: list[AgentToolExecutionRecord]) -> list[BusinessOperationDefinition]:
        return [self.from_tool_record(record) for record in records]
