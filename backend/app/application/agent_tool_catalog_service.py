"""Application service for tool provider catalog and governance."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.agent_tool_execution_service import AgentToolExecutionService
from app.application.permission_service import PermissionService
from app.core.credential_cipher import CredentialCipher
from app.db.models import AgentAppToolGrant, AgentTool, ToolProvider, User
from app.models.schemas.tool_provider import (
    AgentToolBatchPublishRequest,
    AgentToolBatchPublishResponse,
    AgentToolGrantCreate,
    AgentToolGrantListResponse,
    AgentToolGrantReplace,
    AgentToolGrantResponse,
    AgentToolInvocationListResponse,
    AgentToolInvocationResponse,
    AgentToolListResponse,
    AgentToolPublishResponse,
    AgentToolResponse,
    AgentToolSyncResponse,
    AgentToolTestRequest,
    AgentToolTestResponse,
    AgentToolUpdate,
    ToolProviderCreate,
    ToolProviderListResponse,
    ToolProviderResponse,
    ToolProviderTestResponse,
    ToolProviderUpdate,
)
from app.repositories.agent_tool_repository import (
    AgentToolExecutionRecord,
    AgentToolGrantRecord,
    AgentToolInvocationRecord,
    AgentToolRecord,
    AgentToolRepository,
    ToolProviderRecord,
)
from app.services.tool_providers.gateway import ToolProviderGateway
from app.services.tool_providers.schemas import ToolProviderConfig, ToolProviderError


class AgentToolCatalogService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        user: User,
        gateway: ToolProviderGateway | None = None,
    ) -> None:
        self.db = db
        self.user = user
        self.repository = AgentToolRepository(db)
        self.permission_service = PermissionService(db)
        self.gateway = gateway or ToolProviderGateway()
        self.execution_service = AgentToolExecutionService(db, gateway=self.gateway)
        self.credential_cipher = CredentialCipher()

    @staticmethod
    def _not_found(message: str) -> HTTPException:
        return HTTPException(status_code=404, detail=message)

    @staticmethod
    def _bad_request(message: str) -> HTTPException:
        return HTTPException(status_code=400, detail=message)

    async def _ensure_team_access(self, team_id: int) -> None:
        if not await self.permission_service.can_access_team(self.user, team_id):
            raise HTTPException(status_code=403, detail="Team access denied")

    async def _provider_for_access(self, provider_id: int) -> ToolProvider:
        provider = await self.repository.get_provider(provider_id)
        if provider is None:
            raise self._not_found("工具提供方不存在")
        await self._ensure_team_access(provider.team_id)
        return provider

    async def _tool_record_for_access(self, tool_id: int) -> AgentToolRecord:
        record = await self.repository.get_tool_record(tool_id)
        if record is None:
            raise self._not_found("Agent 工具不存在")
        await self._ensure_team_access(record.tool.team_id)
        return record

    async def _ensure_tool_records_access(self, records: list[AgentToolRecord]) -> None:
        for team_id in dict.fromkeys(record.tool.team_id for record in records):
            await self._ensure_team_access(team_id)

    @staticmethod
    def _validate_provider_auth(transport_type: str, auth_type: str, header_name: str | None) -> None:
        if transport_type == "business_http" and auth_type != "bearer":
            raise AgentToolCatalogService._bad_request("业务 HTTP 提供方只支持 Bearer Token")
        if auth_type == "header" and not str(header_name or "").strip():
            raise AgentToolCatalogService._bad_request("自定义鉴权必须填写请求头名称")

    def _provider_config(self, provider: ToolProvider) -> ToolProviderConfig:
        token = None
        if provider.auth_type != "none":
            if not provider.auth_token_encrypted:
                raise ToolProviderError("工具提供方未配置 Service Token")
            token = self.credential_cipher.decrypt(provider.auth_token_encrypted)
        return ToolProviderConfig(
            code=provider.code,
            base_url=provider.base_url,
            transport_type=provider.transport_type,
            auth_type=provider.auth_type,
            auth_header_name=provider.auth_header_name,
            auth_token=token,
        )

    @staticmethod
    def _provider_response(record: ToolProviderRecord | ToolProvider) -> ToolProviderResponse:
        provider = record.provider if isinstance(record, ToolProviderRecord) else record
        return ToolProviderResponse(
            id=provider.id,
            team_id=provider.team_id,
            team_name=record.team_name if isinstance(record, ToolProviderRecord) else None,
            code=provider.code,
            name=provider.name,
            description=provider.description,
            base_url=provider.base_url,
            transport_type=provider.transport_type,
            auth_type=provider.auth_type,
            auth_header_name=provider.auth_header_name,
            has_auth_token=bool(provider.auth_token_encrypted),
            auth_token_masked=(f"****{provider.auth_token_last_four}" if provider.auth_token_last_four else None),
            enabled=provider.enabled,
            health_status=provider.health_status,
            last_checked_at=provider.last_checked_at,
            last_error=provider.last_error,
            tool_count=record.tool_count if isinstance(record, ToolProviderRecord) else 0,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    @staticmethod
    def _tool_response(record: AgentToolRecord) -> AgentToolResponse:
        tool = record.tool
        return AgentToolResponse(
            id=tool.id,
            provider_id=record.provider.id,
            provider_code=record.provider.code,
            provider_name=record.provider.name,
            team_id=tool.team_id,
            team_name=record.team_name,
            external_name=tool.external_name,
            external_display_name=tool.external_display_name,
            external_description=tool.external_description,
            domain=tool.domain,
            action=tool.action,
            read_only=tool.read_only,
            required_permissions=list(tool.required_permissions or []),
            input_schema=tool.input_schema or {},
            output_schema=tool.output_schema or {},
            required_context=list(tool.required_context or []),
            schema_hash=tool.schema_hash,
            sync_status=tool.sync_status,
            last_synced_at=tool.last_synced_at,
            tool_key=tool.tool_key,
            name=tool.name,
            agent_description=tool.agent_description,
            risk_level=tool.risk_level,
            requires_confirmation=tool.requires_confirmation,
            publish_status=tool.publish_status,
            approved_schema_hash=tool.approved_schema_hash,
            last_tested_at=tool.last_tested_at,
            last_test_error=tool.last_test_error,
            created_at=tool.created_at,
            updated_at=tool.updated_at,
        )

    @staticmethod
    def _grant_response(record: AgentToolGrantRecord) -> AgentToolGrantResponse:
        return AgentToolGrantResponse(
            id=record.grant.id,
            project_app_id=record.grant.project_app_id,
            agent_tool_id=record.tool.id,
            tool_key=record.tool.tool_key,
            tool_name=record.tool.name,
            provider_id=record.provider.id,
            provider_name=record.provider.name,
            created_at=record.grant.created_at,
        )

    @staticmethod
    def _invocation_response(record: AgentToolInvocationRecord) -> AgentToolInvocationResponse:
        item = record.invocation
        return AgentToolInvocationResponse(
            **{
                column: getattr(item, column)
                for column in AgentToolInvocationResponse.model_fields
                if hasattr(item, column)
            },
            team_name=record.team_name,
            project_app_name=record.project_app_name,
            provider_name=record.provider_name,
        )

    async def list_providers(self, **filters: Any) -> ToolProviderListResponse:
        team_id = filters.get("team_id")
        if team_id is None:
            raise self._bad_request("team_id is required")
        await self._ensure_team_access(team_id)
        records, total = await self.repository.list_providers(**filters)
        return ToolProviderListResponse(
            items=[self._provider_response(record) for record in records],
            total=total,
            page=filters["page"],
            page_size=filters["page_size"],
        )

    async def create_provider(self, payload: ToolProviderCreate) -> ToolProviderResponse:
        await self._ensure_team_access(payload.team_id)
        self._validate_provider_auth(payload.transport_type, payload.auth_type, payload.auth_header_name)
        if await self.repository.get_provider_by_code(team_id=payload.team_id, code=payload.code):
            raise self._bad_request("同一团队下 Provider code 不能重复")
        data = payload.model_dump(exclude={"auth_token"})
        provider = ToolProvider(**data)
        if payload.auth_token:
            provider.auth_token_encrypted = self.credential_cipher.encrypt(payload.auth_token)
            provider.auth_token_last_four = payload.auth_token[-4:]
        return self._provider_response(await self.repository.save_provider(provider))

    async def update_provider(self, provider_id: int, payload: ToolProviderUpdate) -> ToolProviderResponse:
        provider = await self._provider_for_access(provider_id)
        if payload.team_id != provider.team_id:
            raise self._bad_request("工具提供方不能迁移到其他团队")
        self._validate_provider_auth(payload.transport_type, payload.auth_type, payload.auth_header_name)
        for key, value in payload.model_dump(exclude={"auth_token"}).items():
            setattr(provider, key, value)
        if payload.auth_token:
            provider.auth_token_encrypted = self.credential_cipher.encrypt(payload.auth_token)
            provider.auth_token_last_four = payload.auth_token[-4:]
        provider.health_status = "untested"
        provider.last_error = None
        return self._provider_response(await self.repository.save_provider(provider))

    async def delete_provider(self, provider_id: int) -> None:
        provider = await self._provider_for_access(provider_id)
        await self.repository.delete_provider(provider)

    async def test_provider(self, provider_id: int) -> ToolProviderTestResponse:
        provider = await self._provider_for_access(provider_id)
        started = time.perf_counter()
        try:
            tools = await self.gateway.discover_tools(self._provider_config(provider))
            provider.health_status = "available"
            provider.last_error = None
            message = f"连接成功，发现 {len(tools)} 个工具"
            success = True
        except (ToolProviderError, ValueError) as exc:
            tools = []
            provider.health_status = "error"
            provider.last_error = str(exc)
            message = str(exc)
            success = False
        provider.last_checked_at = datetime.now(timezone.utc)
        await self.repository.save_provider(provider)
        return ToolProviderTestResponse(
            success=success,
            health_status=provider.health_status,
            message=message,
            duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
            tool_count=len(tools),
        )

    async def sync_tools(self, provider_id: int) -> AgentToolSyncResponse:
        provider = await self._provider_for_access(provider_id)
        try:
            discovered = await self.gateway.discover_tools(self._provider_config(provider))
        except (ToolProviderError, ValueError) as exc:
            raise self._bad_request(str(exc)) from exc
        existing = await self.repository.list_tools_for_provider(provider.id)
        by_name = {tool.external_name: tool for tool in existing}
        discovered_names = {item.external_name for item in discovered}
        now = datetime.now(timezone.utc)
        changed: list[AgentTool] = []
        for tool in existing:
            if tool.external_name not in discovered_names and tool.sync_status != "removed":
                tool.sync_status = "removed"
                changed.append(tool)
        for item in discovered:
            tool = by_name.get(item.external_name)
            if tool is None:
                tool = AgentTool(
                    provider_id=provider.id,
                    team_id=provider.team_id,
                    external_name=item.external_name,
                    external_display_name=item.external_display_name,
                    tool_key=await self._new_tool_key(provider, item.external_name),
                    name=item.external_display_name,
                    agent_description=item.description,
                    publish_status="draft",
                )
                changed.append(tool)
            else:
                uses_source_name = tool.name in {
                    tool.external_name,
                    tool.external_display_name,
                }
                if uses_source_name:
                    tool.name = item.external_display_name
                if tool.schema_hash != item.schema_hash and tool.publish_status == "published":
                    tool.publish_status = "needs_review"
            tool.external_description = item.description
            tool.external_display_name = item.external_display_name
            tool.domain = item.domain
            tool.action = item.action
            tool.read_only = item.read_only
            tool.required_permissions = item.required_permissions
            tool.input_schema = item.input_schema
            tool.output_schema = item.output_schema
            tool.required_context = item.required_context
            tool.raw_manifest = item.raw_manifest
            tool.schema_hash = item.schema_hash
            tool.sync_status = "active"
            tool.last_synced_at = now
            if tool not in changed:
                changed.append(tool)
        await self.repository.save_tools(changed)
        return AgentToolSyncResponse(
            provider_id=provider.id,
            synced_count=len(discovered),
            message=f"已同步 {len(discovered)} 个工具",
        )

    async def _new_tool_key(self, provider: ToolProvider, external_name: str) -> str:
        base = re.sub(r"[^a-z0-9_]+", "_", f"{provider.code}_{external_name}".lower()).strip("_")
        if not base or not base[0].isalpha():
            base = f"tool_{base}"
        candidate = base[:120]
        index = 2
        while await self.repository.get_tool_by_key(team_id=provider.team_id, tool_key=candidate):
            suffix = f"_{index}"
            candidate = f"{base[:120 - len(suffix)]}{suffix}"
            index += 1
        return candidate

    async def list_tools(self, **filters: Any) -> AgentToolListResponse:
        team_id = filters.get("team_id")
        provider_id = filters.get("provider_id")
        if team_id is None:
            raise self._bad_request("team_id is required")
        await self._ensure_team_access(team_id)
        if provider_id is not None:
            provider = await self._provider_for_access(provider_id)
            if provider.team_id != team_id:
                raise self._bad_request("工具提供方不属于当前团队")
        records, total = await self.repository.list_tools(**filters)
        return AgentToolListResponse(
            items=[self._tool_response(record) for record in records],
            total=total,
            page=filters["page"],
            page_size=filters["page_size"],
        )

    async def get_tool(self, tool_id: int) -> AgentToolResponse:
        record = await self._tool_record_for_access(tool_id)
        return self._tool_response(record)

    async def update_tool(self, tool_id: int, payload: AgentToolUpdate) -> AgentToolResponse:
        record = await self._tool_record_for_access(tool_id)
        for key, value in payload.model_dump().items():
            setattr(record.tool, key, value)
        await self.repository.save_tool(record.tool)
        refreshed = await self.repository.get_tool_record(tool_id)
        return self._tool_response(refreshed)

    async def test_tool(self, tool_id: int, payload: AgentToolTestRequest) -> AgentToolTestResponse:
        record = await self._tool_record_for_access(tool_id)
        result = await self.execution_service.execute(
            record=AgentToolExecutionRecord(tool=record.tool, provider=record.provider),
            arguments=payload.arguments,
            context=payload.context,
            call_source="admin_test",
            project_app_id=None,
        )
        record.tool.last_tested_at = datetime.now(timezone.utc)
        record.tool.last_test_error = None if result.success else result.message
        await self.repository.save_tool(record.tool)
        return AgentToolTestResponse(
            success=result.success,
            message=result.message or ("工具执行成功" if result.success else "工具执行失败"),
            duration_ms=result.duration_ms,
            data=result.data,
            error_code=result.error_code,
        )

    async def publish_tool(self, tool_id: int) -> AgentToolPublishResponse:
        record = await self._tool_record_for_access(tool_id)
        if record.tool.sync_status != "active":
            raise self._bad_request("只有同步状态正常的工具可以发布")
        record.tool.publish_status = "published"
        record.tool.approved_schema_hash = record.tool.schema_hash
        await self.repository.save_tool(record.tool)
        return AgentToolPublishResponse(id=tool_id, publish_status="published", message="工具已发布")

    async def batch_publish_tools(
        self,
        payload: AgentToolBatchPublishRequest,
    ) -> AgentToolBatchPublishResponse:
        tool_ids = sorted(set(payload.tool_ids))
        records = await self.repository.get_tool_records_by_ids(tool_ids)
        if len(records) != len(tool_ids):
            raise self._not_found("部分工具不存在")
        await self._ensure_tool_records_access(records)
        if any(record.tool.sync_status != "active" for record in records):
            raise self._bad_request("只有同步状态正常的工具可以发布")
        for record in records:
            record.tool.publish_status = "published"
            record.tool.approved_schema_hash = record.tool.schema_hash
        await self.repository.save_tools([record.tool for record in records])
        return AgentToolBatchPublishResponse(
            published_ids=tool_ids,
            published_count=len(tool_ids),
            message=f"已发布 {len(tool_ids)} 个工具",
        )

    async def unpublish_tool(self, tool_id: int) -> AgentToolPublishResponse:
        record = await self._tool_record_for_access(tool_id)
        record.tool.publish_status = "draft"
        await self.repository.save_tool(record.tool)
        return AgentToolPublishResponse(id=tool_id, publish_status="draft", message="工具已下线")

    async def list_grants(self, *, project_id: int, app_id: int) -> AgentToolGrantListResponse:
        app = await self.repository.get_project_app(project_id=project_id, app_id=app_id)
        team_id = await self.repository.get_project_app_team_id(project_id=project_id, app_id=app_id)
        if app is None or team_id is None:
            raise self._not_found("应用端不存在")
        await self._ensure_team_access(team_id)
        records = await self.repository.list_grants(project_app_id=app.id)
        return AgentToolGrantListResponse(items=[self._grant_response(record) for record in records])

    async def create_grant(
        self,
        *,
        project_id: int,
        app_id: int,
        payload: AgentToolGrantCreate,
    ) -> AgentToolGrantResponse:
        app = await self.repository.get_project_app(project_id=project_id, app_id=app_id)
        team_id = await self.repository.get_project_app_team_id(project_id=project_id, app_id=app_id)
        tool_record = await self.repository.get_tool_record(payload.agent_tool_id)
        if app is None or team_id is None:
            raise self._not_found("应用端不存在")
        await self._ensure_team_access(team_id)
        if tool_record is None or tool_record.tool.team_id != team_id:
            raise self._bad_request("只能授权当前团队的工具")
        existing = await self.repository.get_grant_by_tool(
            project_app_id=app.id,
            agent_tool_id=payload.agent_tool_id,
        )
        grant = existing or await self.repository.save_grant(
            AgentAppToolGrant(project_app_id=app.id, agent_tool_id=payload.agent_tool_id)
        )
        records = await self.repository.list_grants(project_app_id=app.id)
        return self._grant_response(next(record for record in records if record.grant.id == grant.id))

    async def replace_grants(
        self,
        *,
        project_id: int,
        app_id: int,
        payload: AgentToolGrantReplace,
    ) -> AgentToolGrantListResponse:
        app = await self.repository.get_project_app(project_id=project_id, app_id=app_id)
        team_id = await self.repository.get_project_app_team_id(project_id=project_id, app_id=app_id)
        if app is None or team_id is None:
            raise self._not_found("应用端不存在")
        await self._ensure_team_access(team_id)

        tool_ids = sorted(set(payload.agent_tool_ids))
        records = await self.repository.get_tool_records_by_ids(tool_ids)
        if len(records) != len(tool_ids):
            raise self._bad_request("包含不存在的 Agent 工具")
        for record in records:
            if record.tool.team_id != team_id:
                raise self._bad_request("只能授权当前团队的工具")
            if record.tool.publish_status != "published":
                raise self._bad_request(f"工具“{record.tool.name}”尚未发布")
            if record.tool.sync_status != "active":
                raise self._bad_request(f"工具“{record.tool.name}”同步状态正常后才能授权")
            if record.tool.schema_hash != record.tool.approved_schema_hash:
                raise self._bad_request(f"工具“{record.tool.name}”的 Schema 尚未批准")
            if not record.provider.enabled:
                raise self._bad_request(f"工具“{record.tool.name}”的提供方未启用")

        await self.repository.replace_grants(project_app_id=app.id, agent_tool_ids=tool_ids)
        grants = await self.repository.list_grants(project_app_id=app.id)
        return AgentToolGrantListResponse(items=[self._grant_response(record) for record in grants])

    async def delete_grant(self, *, project_id: int, app_id: int, grant_id: int) -> None:
        app = await self.repository.get_project_app(project_id=project_id, app_id=app_id)
        team_id = await self.repository.get_project_app_team_id(project_id=project_id, app_id=app_id)
        grant = await self.repository.get_grant(grant_id)
        if app is None or team_id is None or grant is None or grant.project_app_id != app.id:
            raise self._not_found("工具授权不存在")
        await self._ensure_team_access(team_id)
        await self.repository.delete_grant(grant)

    async def list_invocations(self, **filters: Any) -> AgentToolInvocationListResponse:
        team_id = filters.get("team_id")
        if team_id is None:
            raise self._bad_request("team_id is required")
        await self._ensure_team_access(team_id)
        records, total = await self.repository.list_invocations(**filters)
        return AgentToolInvocationListResponse(
            items=[self._invocation_response(record) for record in records],
            total=total,
            page=filters["page"],
            page_size=filters["page_size"],
        )
