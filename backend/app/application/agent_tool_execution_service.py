"""Execute governed Agent tools through protocol-neutral providers."""

from __future__ import annotations

from typing import Any

from jsonschema import exceptions as jsonschema_exceptions
from jsonschema import validators
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credential_cipher import CredentialCipher
from app.db.models import AgentToolInvocation
from app.repositories.agent_tool_repository import (
    AgentToolExecutionRecord,
    AgentToolRepository,
)
from app.services.tool_providers.gateway import ToolProviderGateway
from app.services.tool_providers.schemas import (
    ToolCallResult,
    ToolProviderConfig,
    ToolProviderError,
)
from app.utils.time import utc_now

_CONTEXT_LOCATIONS = {
    "external_user_id": "subject",
    "project_app_id": "source",
    "project_id": "source",
    "request_id": "source",
    "session_id": "source",
    "store_id": "scope",
}


class AgentToolExecutionService:
    """Validate, call and audit one published or administratively tested tool."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        gateway: ToolProviderGateway | None = None,
    ) -> None:
        self.repository = AgentToolRepository(db)
        self.gateway = gateway or ToolProviderGateway()
        self.credential_cipher = CredentialCipher()

    async def execute(
        self,
        *,
        record: AgentToolExecutionRecord,
        arguments: dict[str, Any],
        context: dict[str, Any],
        call_source: str,
        project_app_id: int | None,
        actor_user_id: int | None = None,
        confirmed: bool = False,
    ) -> ToolCallResult:
        tool = record.tool
        validation_error = self._validate_arguments(tool.input_schema, arguments)
        if validation_error:
            return ToolCallResult(
                success=False,
                error_code="INVALID_PARAMS",
                message=validation_error,
                retryable=True,
            )
        missing_context = [
            field
            for field in list(tool.required_context or [])
            if self._context_value(context, field) in {None, ""}
        ]
        if missing_context:
            return ToolCallResult(
                success=False,
                error_code="CONTEXT_REQUIRED",
                message=f"缺少可信上下文：{', '.join(missing_context)}",
            )
        try:
            provider_config = self._provider_config(record)
            result = await self.gateway.call_tool(
                provider_config,
                tool.external_name,
                arguments,
                context,
            )
        except ToolProviderError as exc:
            result = ToolCallResult(
                success=False,
                error_code="UPSTREAM_ERROR",
                message=str(exc),
            )
        await self._audit(
            record=record,
            arguments=arguments,
            context=context,
            result=result,
            call_source=call_source,
            project_app_id=project_app_id,
            actor_user_id=actor_user_id,
            confirmed=confirmed,
        )
        return result

    def _provider_config(self, record: AgentToolExecutionRecord) -> ToolProviderConfig:
        provider = record.provider
        token = None
        if provider.auth_type != "none":
            if not provider.auth_token_encrypted:
                raise ToolProviderError("工具提供方未配置 Service Token")
            try:
                token = self.credential_cipher.decrypt(provider.auth_token_encrypted)
            except ValueError as exc:
                raise ToolProviderError("工具提供方 Service Token 无法解密") from exc
        return ToolProviderConfig(
            code=provider.code,
            base_url=provider.base_url,
            transport_type=provider.transport_type,
            auth_type=provider.auth_type,
            auth_header_name=provider.auth_header_name,
            auth_token=token,
        )

    @staticmethod
    def _validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> str | None:
        try:
            validator_class = validators.validator_for(schema)
            validator_class.check_schema(schema)
            error = next(iter(validator_class(schema).iter_errors(arguments)), None)
        except jsonschema_exceptions.SchemaError:
            return "工具参数 Schema 无效"
        return error.message if error else None

    @staticmethod
    def _context_value(context: dict[str, Any], field: str) -> Any:
        location = _CONTEXT_LOCATIONS.get(field)
        section = context.get(location) if location else None
        return section.get(field) if isinstance(section, dict) else None

    async def _audit(
        self,
        *,
        record: AgentToolExecutionRecord,
        arguments: dict[str, Any],
        context: dict[str, Any],
        result: ToolCallResult,
        call_source: str,
        project_app_id: int | None,
        actor_user_id: int | None,
        confirmed: bool,
    ) -> None:
        tool = record.tool
        provider = record.provider
        subject = context.get("subject") if isinstance(context.get("subject"), dict) else {}
        source = context.get("source") if isinstance(context.get("source"), dict) else {}
        try:
            await self.repository.create_invocation(
                AgentToolInvocation(
                    team_id=tool.team_id,
                    provider_id=provider.id,
                    agent_tool_id=tool.id,
                    project_app_id=project_app_id,
                    provider_code=provider.code,
                    external_name=tool.external_name,
                    tool_key=tool.tool_key,
                    schema_hash=tool.schema_hash,
                    session_id=str(source.get("session_id") or "") or None,
                    trace_id=str(source.get("trace_id") or "") or None,
                    request_id=str(source.get("request_id") or "") or None,
                    actor_user_id=actor_user_id,
                    external_user_id=str(subject.get("external_user_id") or "") or None,
                    call_source=call_source,
                    status="success" if result.success else "error",
                    error_code=result.error_code,
                    error_message=result.message if not result.success else None,
                    duration_ms=result.duration_ms,
                    request_summary={"argument_keys": sorted(arguments)},
                    response_summary={"data_keys": sorted(result.data)},
                    confirmed=confirmed,
                    confirmed_at=utc_now() if confirmed else None,
                )
            )
        except Exception:
            await self.repository.db.rollback()
            logger.exception("[agent_tool] failed to persist invocation audit")
