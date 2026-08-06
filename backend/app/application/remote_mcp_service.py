"""Application service for the remote, app-scoped MCP Agent entrypoint."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.agent.input_builder import AgentRunRequest
from app.application.agent.run_service import get_agent_run_service
from app.application.project_app_access_service import ProjectAppAccessService
from app.repositories.project_app_access_repository import ProjectAppAccessRepository
from app.repositories.project_repository import ProjectAppRuntimeRecord, ProjectRepository


class RemoteMcpAuthenticationError(ValueError):
    """Raised when an MCP bearer credential cannot be used."""


class RemoteMcpConfigurationError(ValueError):
    """Raised when the MCP application is not ready for knowledge QA."""


@dataclass(frozen=True, slots=True)
class RemoteMcpContext:
    """Trusted application scope resolved from one MCP request."""

    client_id: str
    project_app_id: int
    team_id: int
    product_id: int
    project_id: int
    knowledge_base_id: int | None
    category_id: int | None
    assistant_id: int | None
    assistant_name: str | None
    assistant_llm_model_key: str | None
    assistant_persona_prompt: str | None
    assistant_rule_template: str | None
    mcp_session_id: str | None


def _split_client_credential(token: str) -> tuple[str, str]:
    client_id, separator, client_secret = str(token or "").partition(".")
    if not separator or not client_id or not client_secret:
        raise RemoteMcpAuthenticationError("Invalid MCP bearer credential")
    return client_id, client_secret


async def authenticate_remote_mcp(
    db: AsyncSession,
    *,
    bearer_token: str,
    mcp_session_id: str | None,
) -> RemoteMcpContext:
    """Validate a ProjectApp credential and derive its Agent capabilities."""

    client_id, client_secret = _split_client_credential(bearer_token)
    credential = await ProjectAppAccessRepository(db).get_by_client_id(client_id)
    if credential is None:
        raise RemoteMcpAuthenticationError("Invalid MCP bearer credential")
    if not credential.enabled:
        raise RemoteMcpAuthenticationError("Project application access is disabled")
    if not ProjectAppAccessService(db).verify_client_secret(credential, client_secret):
        raise RemoteMcpAuthenticationError("Invalid MCP bearer credential")

    runtime = await ProjectRepository(db).get_runtime_by_app_id(
        project_app_id=int(credential.project_app_id),
        active_only=True,
    )
    if runtime is None:
        raise RemoteMcpAuthenticationError("Active project application not found")
    if runtime.app.terminal_type != "mcp":
        raise RemoteMcpAuthenticationError("Credential is not valid for MCP access")

    if runtime.app.knowledge_base_id is None:
        raise RemoteMcpConfigurationError("MCP application knowledge base is not configured")

    return _build_context(
        credential.client_id,
        runtime,
        mcp_session_id=mcp_session_id,
    )


def _build_context(
    client_id: str,
    runtime: ProjectAppRuntimeRecord,
    *,
    mcp_session_id: str | None,
) -> RemoteMcpContext:
    assistant = runtime.assistant
    return RemoteMcpContext(
        client_id=str(client_id),
        project_app_id=int(runtime.app.id),
        team_id=int(runtime.project.team_id),
        product_id=int(runtime.product.id),
        project_id=int(runtime.project.id),
        knowledge_base_id=(
            int(runtime.app.knowledge_base_id)
            if runtime.app.knowledge_base_id is not None
            else None
        ),
        category_id=(int(runtime.app.category_id) if runtime.app.category_id is not None else None),
        assistant_id=int(assistant.id) if assistant is not None else None,
        assistant_name=assistant.name if assistant is not None else None,
        assistant_llm_model_key=(
            getattr(assistant, "llm_model_key", None) if assistant is not None else None
        ),
        assistant_persona_prompt=(
            getattr(assistant, "persona_prompt", None) if assistant is not None else None
        ),
        assistant_rule_template=(
            getattr(assistant, "rule_template", None) if assistant is not None else None
        ),
        mcp_session_id=mcp_session_id,
    )


def _agent_session_id(context: RemoteMcpContext) -> str:
    raw_session_id = context.mcp_session_id or context.client_id
    digest = hashlib.sha256(raw_session_id.encode("utf-8")).hexdigest()[:40]
    return f"mcp:{context.project_app_id}:{digest}"


async def chat_remote_mcp(context: RemoteMcpContext, *, message: str):
    """Run one remote MCP message through the persistent Agent use case."""

    request = AgentRunRequest(
        query=message,
        session_id=_agent_session_id(context),
        team_id=context.team_id,
        external_user_id=f"mcp:{context.client_id}",
        product_id=context.product_id,
        project_id=context.project_id,
        project_app_id=context.project_app_id,
        knowledge_base_id=context.knowledge_base_id,
        category_id=context.category_id,
        assistant_id=context.assistant_id,
        assistant_name=context.assistant_name,
        assistant_llm_model_key=context.assistant_llm_model_key,
        assistant_persona_prompt=context.assistant_persona_prompt,
        assistant_rule_template=context.assistant_rule_template,
        trusted_scope={
            "source": "remote_mcp",
            "project_app_id": context.project_app_id,
        },
        source_surface="remote_mcp",
    )
    return await get_agent_run_service().invoke(request, user_id=None)
