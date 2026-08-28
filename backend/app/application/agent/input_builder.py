"""Prepare trusted input before entering the Agent graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.agents.common.runtime_context import build_runtime_context
from app.agents.main.nodes.utils import normalize_query
from app.agents.main.state import AgentInput
from app.services.document_lifecycle import VISIBLE_ASK_DOCUMENT_STATUSES


@dataclass(frozen=True, slots=True)
class AgentRunRequest:
    """Transport-neutral request accepted by the Agent application layer."""

    query: str
    session_id: str | None = None
    team_id: int | None = None
    external_user_id: str | None = None
    external_user_name: str | None = None
    product_id: int | None = None
    project_id: int | None = None
    project_app_id: int | None = None
    knowledge_base_id: int | None = None
    category_id: int | None = None
    store_id: str | None = None
    trusted_scope: dict[str, Any] | None = None
    allowed_document_statuses: list[str] | None = None
    assistant_id: int | None = None
    assistant_name: str | None = None
    assistant_llm_model_key: str | None = None
    assistant_persona_prompt: str | None = None
    assistant_rule_template: str | None = None
    page_context: dict[str, Any] | None = None
    page_config: dict[str, Any] | None = None
    source_surface: str = "unknown"


def prepare_agent_input(
    *,
    query: str,
    session_id: str | None = None,
    request_id: str | None = None,
    run_id: str | None = None,
    user_id: int | None = None,
    team_id: int | None = None,
    external_user_id: str | None = None,
    external_user_name: str | None = None,
    product_id: int | None = None,
    project_id: int | None = None,
    project_app_id: int | None = None,
    knowledge_base_id: int | None = None,
    category_id: int | None = None,
    store_id: str | None = None,
    trusted_scope: dict[str, Any] | None = None,
    allowed_document_statuses: list[str] | None = None,
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    assistant_id: int | None = None,
    assistant_name: str | None = None,
    assistant_llm_model_key: str | None = None,
    assistant_persona_prompt: str | None = None,
    assistant_rule_template: str | None = None,
    page_context: dict[str, Any] | None = None,
    page_config: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentInput:
    """Normalize transport data and snapshot trusted execution context once."""

    normalized_query = normalize_query(query)
    if not normalized_query:
        raise ValueError("query is required")
    resolved_run_id = run_id or uuid4().hex
    resolved_request_id = request_id or uuid4().hex
    resolved_session_id = session_id or uuid4().hex
    return {
        "request_id": resolved_request_id,
        "run_id": resolved_run_id,
        "query": normalized_query,
        "identity": {
            key: value
            for key, value in {
                "user_id": user_id,
                "team_id": team_id,
                "external_user_id": external_user_id,
                "external_user_name": external_user_name,
            }.items()
            if value is not None
        },
        "resources": {
            key: value
            for key, value in {
                "product_id": product_id,
                "project_id": project_id,
                "project_app_id": project_app_id,
                "knowledge_base_id": knowledge_base_id,
                "category_id": category_id,
                "store_id": store_id,
                "trusted_scope": dict(trusted_scope or {}),
                "allowed_document_statuses": list(
                    VISIBLE_ASK_DOCUMENT_STATUSES
                    if allowed_document_statuses is None
                    else allowed_document_statuses
                ),
            }.items()
            if value is not None
        },
        "conversation": {
            "session_id": resolved_session_id,
            "history": list(chat_history or []),
            **({"summary": memory_summary} if memory_summary else {}),
        },
        "assistant": {
            key: value
            for key, value in {
                "id": assistant_id,
                "name": assistant_name,
                "model_key": assistant_llm_model_key,
                "persona_prompt": assistant_persona_prompt,
                "rule_template": assistant_rule_template,
            }.items()
            if value is not None
        },
        "page_context": dict(page_context or {}),
        "page_config": dict(page_config or {}),
        "runtime_context": build_runtime_context(),
        "metadata": {"workflow": "agent", **dict(metadata or {})},
    }
