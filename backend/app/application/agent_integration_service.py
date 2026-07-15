"""Application service for Agent integration management."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.business_operations.mcp_tool_gateway import McpToolGateway
from app.core.credential_cipher import CredentialCipher
from app.db.models import AgentAppToolSetBinding, AgentTool, McpServer, McpTool
from app.models.schemas.agent_integration import (
    AgentAppToolSetBindingCreate,
    AgentAppToolSetBindingListResponse,
    AgentAppToolSetBindingResponse,
    AgentToolCallLogListResponse,
    AgentToolCallLogResponse,
    AgentToolCreate,
    AgentToolListResponse,
    AgentToolPublishResponse,
    AgentToolResponse,
    AgentToolTestRequest,
    AgentToolTestResponse,
    AgentToolUpdate,
    McpServerCreate,
    McpServerListResponse,
    McpServerResponse,
    McpServerTestResponse,
    McpServerUpdate,
    McpToolEnabledUpdate,
    McpToolListResponse,
    McpToolResponse,
    McpToolSyncResponse,
)
from app.repositories.agent_integration_repository import (
    AgentAppToolSetBindingRecord,
    AgentIntegrationRepository,
    AgentToolCallLogRecord,
    AgentToolRecord,
    McpServerRecord,
    McpToolRecord,
)
from app.utils.time import utc_now

_TOOL_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,119}$")


class AgentIntegrationService:
    """Coordinate MCP server management and Agent tool governance."""

    def __init__(self, db: AsyncSession, *, mcp_gateway: McpToolGateway | None = None) -> None:
        self.db = db
        self.repository = AgentIntegrationRepository(db)
        self.mcp_gateway = mcp_gateway or McpToolGateway()
        self.credential_cipher = CredentialCipher()

    @staticmethod
    def _not_found(message: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

    @staticmethod
    def _bad_request(message: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    @staticmethod
    def _normalize_tool_key(value: str) -> str:
        normalized = AgentIntegrationRepository.normalize_key(value)
        if not _TOOL_KEY_PATTERN.match(normalized):
            raise AgentIntegrationService._bad_request("工具 Key 必须以小写字母开头，且只能包含小写字母、数字和下划线。")
        return normalized

    def _to_server_response(self, record: McpServerRecord | McpServer) -> McpServerResponse:
        if isinstance(record, McpServerRecord):
            server = record.server
            team_name = record.team_name
            tool_count = record.tool_count
        else:
            server = record
            team_name = None
            tool_count = 0
        return McpServerResponse(
            id=server.id,
            team_id=server.team_id,
            team_name=team_name,
            name=server.name,
            description=server.description,
            environment=server.environment,
            endpoint_url=server.endpoint_url,
            transport_type=server.transport_type,
            auth_type=server.auth_type,
            auth_header_name=server.auth_header_name,
            has_auth_token=bool(server.auth_token_encrypted),
            auth_token_masked=(
                f"****{server.auth_token_last_four}"
                if server.auth_token_encrypted and server.auth_token_last_four
                else None
            ),
            enabled=server.enabled,
            status=server.status,
            last_checked_at=server.last_checked_at,
            last_error=server.last_error,
            tool_count=tool_count,
            created_at=server.created_at,
            updated_at=server.updated_at,
        )

    @staticmethod
    def _to_mcp_tool_response(record: McpToolRecord) -> McpToolResponse:
        tool = record.tool
        return McpToolResponse(
            id=tool.id,
            mcp_server_id=tool.mcp_server_id,
            server_name=record.server_name,
            raw_name=tool.raw_name,
            raw_description=tool.raw_description,
            input_schema=tool.input_schema or {},
            output_schema=tool.output_schema or {},
            schema_hash=tool.schema_hash,
            sync_status=tool.sync_status,
            raw_payload=tool.raw_payload or {},
            last_synced_at=tool.last_synced_at,
            agent_tool_id=record.agent_tool_id,
            agent_tool_status=record.agent_tool_status,
            agent_tool_enabled=record.agent_tool_enabled,
            created_at=tool.created_at,
            updated_at=tool.updated_at,
        )

    @staticmethod
    def _to_agent_tool_response(record: AgentToolRecord) -> AgentToolResponse:
        tool = record.tool
        mcp_tool = record.mcp_tool
        return AgentToolResponse(
            id=tool.id,
            team_id=tool.team_id,
            team_name=record.team_name,
            mcp_tool_id=tool.mcp_tool_id,
            mcp_server_id=record.mcp_server.id if record.mcp_server else None,
            mcp_server_name=record.mcp_server.name if record.mcp_server else None,
            mcp_tool_name=mcp_tool.raw_name if mcp_tool else None,
            tool_key=tool.tool_key,
            name=tool.name,
            description=tool.description,
            agent_description=tool.agent_description,
            params_schema=tool.params_schema or (mcp_tool.input_schema if mcp_tool else {}),
            response_schema=tool.response_schema or (mcp_tool.output_schema if mcp_tool else {}),
            tool_type=tool.tool_type,
            risk_level=tool.risk_level,
            requires_confirmation=tool.requires_confirmation,
            enabled=tool.enabled,
            status=tool.status,
            last_tested_at=tool.last_tested_at,
            last_test_error=tool.last_test_error,
            created_at=tool.created_at,
            updated_at=tool.updated_at,
        )

    @staticmethod
    def _to_tool_set_binding_response(
        record: AgentAppToolSetBindingRecord,
    ) -> AgentAppToolSetBindingResponse:
        binding = record.binding
        server = record.mcp_server
        return AgentAppToolSetBindingResponse(
            id=binding.id,
            project_app_id=binding.project_app_id,
            mcp_server_id=server.id,
            mcp_server_name=server.name,
            mcp_server_description=server.description,
            tool_count=record.tool_count,
            enabled=binding.enabled,
            unavailable_reason=record.unavailable_reason,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
        )

    @staticmethod
    def _to_log_response(record: AgentToolCallLogRecord) -> AgentToolCallLogResponse:
        log = record.log
        return AgentToolCallLogResponse(
            id=log.id,
            team_id=log.team_id,
            team_name=record.team_name,
            project_app_id=log.project_app_id,
            project_app_name=record.project_app_name,
            agent_tool_id=log.agent_tool_id,
            mcp_server_id=log.mcp_server_id,
            mcp_server_name=record.mcp_server_name,
            session_id=log.session_id,
            trace_id=log.trace_id,
            actor_user_id=log.actor_user_id,
            external_user_id=log.external_user_id,
            tool_key=log.tool_key,
            mcp_tool_name=log.mcp_tool_name,
            status=log.status,
            duration_ms=log.duration_ms,
            request_payload=log.request_payload or {},
            response_payload=log.response_payload or {},
            error_message=log.error_message,
            confirmed=log.confirmed,
            confirmed_at=log.confirmed_at,
            created_at=log.created_at,
        )

    async def list_mcp_servers(self, *, team_id: int | None, keyword: str | None, status: str, page: int, page_size: int) -> McpServerListResponse:
        records, total = await self.repository.list_mcp_servers(team_id=team_id, keyword=keyword, status=status, page=page, page_size=page_size)
        return McpServerListResponse(items=[self._to_server_response(record) for record in records], total=total, page=page, page_size=page_size)

    async def create_mcp_server(self, payload: McpServerCreate) -> McpServerResponse:
        data = payload.model_dump(exclude={"auth_token"})
        token = (payload.auth_token or "").strip()
        if payload.auth_type != "none" and not token:
            raise self._bad_request("启用 MCP 鉴权时必须填写内部服务 Token。")
        server = McpServer(**data)
        if token:
            server.auth_token_encrypted = self.credential_cipher.encrypt(token)
            server.auth_token_last_four = token[-4:]
        saved = await self.repository.create_mcp_server(server)
        await self.db.commit()
        await self.db.refresh(saved)
        return self._to_server_response(saved)

    async def update_mcp_server(self, server_id: int, payload: McpServerUpdate) -> McpServerResponse:
        server = await self.repository.get_mcp_server(server_id)
        if server is None:
            raise self._not_found("MCP 服务不存在。")
        data = payload.model_dump(exclude={"auth_token"})
        for key, value in data.items():
            setattr(server, key, value)
        token = (payload.auth_token or "").strip()
        if payload.auth_type == "none":
            server.auth_token_encrypted = None
            server.auth_token_last_four = None
        elif token:
            server.auth_token_encrypted = self.credential_cipher.encrypt(token)
            server.auth_token_last_four = token[-4:]
        elif not server.auth_token_encrypted:
            raise self._bad_request("启用 MCP 鉴权时必须填写内部服务 Token。")
        server.status = "untested"
        server.last_error = None
        await self.db.commit()
        await self.db.refresh(server)
        return self._to_server_response(server)

    async def delete_mcp_server(self, server_id: int) -> None:
        server = await self.repository.get_mcp_server(server_id)
        if server is None:
            raise self._not_found("MCP 服务不存在。")
        await self.repository.delete_mcp_server(server)

    async def test_mcp_server(self, server_id: int) -> McpServerTestResponse:
        server = await self.repository.get_mcp_server(server_id)
        if server is None:
            raise self._not_found("MCP 服务不存在。")
        service_token = await self._get_service_token(server)
        success, _http_status, duration_ms, message, tools = await self.mcp_gateway.test_server(
            server,
            service_token=service_token,
        )
        server.status = "available" if success else "error"
        server.last_checked_at = utc_now()
        server.last_error = None if success else message
        if success:
            count = await self._sync_discovered_tools(server=server, tools=tools)
            message = f"MCP 服务连接成功，已同步 {count} 个工具。"
        await self.db.commit()
        return McpServerTestResponse(success=success, status=server.status, message=message, duration_ms=duration_ms, tool_count=len(tools))

    async def sync_mcp_tools(self, server_id: int) -> McpToolSyncResponse:
        server = await self.repository.get_mcp_server(server_id)
        if server is None:
            raise self._not_found("MCP 服务不存在。")
        service_token = await self._get_service_token(server)
        success, _http_status, _duration_ms, message, tools = await self.mcp_gateway.test_server(
            server,
            service_token=service_token,
        )
        if not success:
            server.status = "error"
            server.last_checked_at = utc_now()
            server.last_error = message
            await self.db.commit()
            raise self._bad_request(message)
        count = await self._sync_discovered_tools(server=server, tools=tools)
        server.status = "available"
        server.last_checked_at = utc_now()
        server.last_error = None
        await self.db.commit()
        return McpToolSyncResponse(server_id=server.id, synced_count=count, message=f"已同步 {count} 个 MCP 工具。")

    async def _get_service_token(self, server: McpServer) -> str | None:
        if str(server.auth_type or "none").strip().lower() == "none":
            return None
        if not server.auth_token_encrypted:
            raise self._bad_request("MCP 服务未配置内部服务 Token。")
        try:
            return self.credential_cipher.decrypt(server.auth_token_encrypted)
        except ValueError as exc:
            raise self._bad_request("MCP 服务 Token 无法解密，请重新填写。") from exc

    async def _sync_discovered_tools(self, *, server: McpServer, tools: list[dict[str, Any]]) -> int:
        normalized_tools = [self._normalize_mcp_tool_payload(item) for item in tools]
        count = await self.repository.upsert_mcp_tools(server_id=server.id, tools=normalized_tools)
        synced_tools = await self.repository.list_synced_mcp_tools_for_server(server_id=server.id)
        existing_agent_tools = await self.repository.list_agent_tools_for_mcp_server(server_id=server.id)
        agent_tools_by_mcp_id = {item.mcp_tool_id: item for item in existing_agent_tools}

        for mcp_tool in synced_tools:
            agent_tool = agent_tools_by_mcp_id.get(mcp_tool.id)
            if agent_tool is None:
                agent_tool = AgentTool(
                    team_id=server.team_id,
                    mcp_tool_id=mcp_tool.id,
                    tool_key=await self._build_synced_tool_key(server=server, mcp_tool=mcp_tool),
                    name=mcp_tool.raw_name[:100],
                    tool_type="mcp",
                    risk_level="low",
                    requires_confirmation=False,
                    enabled=False,
                    status="draft",
                )
                self.db.add(agent_tool)
            agent_tool.description = mcp_tool.raw_description
            agent_tool.agent_description = mcp_tool.raw_description
            agent_tool.params_schema = mcp_tool.input_schema or {}
            agent_tool.response_schema = mcp_tool.output_schema or {}
            agent_tool.status = "published" if agent_tool.enabled else "draft"
        await self.db.commit()
        return count

    async def _build_synced_tool_key(self, *, server: McpServer, mcp_tool: McpTool) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", mcp_tool.raw_name.strip().lower()).strip("_")
        if not normalized or not normalized[0].isalpha():
            normalized = f"mcp_{normalized}" if normalized else "mcp_tool"
        normalized = normalized[:120].rstrip("_")
        if len(normalized) < 2:
            normalized = f"mcp_{mcp_tool.id}"
        existing = await self.repository.get_agent_tool_by_key(team_id=server.team_id, tool_key=normalized)
        if existing is None or existing.mcp_tool_id == mcp_tool.id:
            return normalized
        suffix = f"_{mcp_tool.id}"
        return f"{normalized[: 120 - len(suffix)].rstrip('_')}{suffix}"

    @staticmethod
    def _normalize_mcp_tool_payload(tool: dict[str, Any]) -> dict[str, Any]:
        input_schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
        output_schema = tool.get("outputSchema") if isinstance(tool.get("outputSchema"), dict) else {}
        raw_name = str(tool.get("name") or "").strip()
        schema_source = json.dumps({"name": raw_name, "input": input_schema, "output": output_schema}, sort_keys=True, ensure_ascii=False)
        return {
            "raw_name": raw_name,
            "raw_description": str(tool.get("description") or "").strip() or None,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "schema_hash": hashlib.sha256(schema_source.encode("utf-8")).hexdigest(),
            "raw_payload": tool,
        }

    async def list_mcp_tools(self, *, team_id: int | None, server_id: int | None, keyword: str | None, page: int, page_size: int) -> McpToolListResponse:
        records, total = await self.repository.list_mcp_tools(team_id=team_id, server_id=server_id, keyword=keyword, page=page, page_size=page_size)
        return McpToolListResponse(items=[self._to_mcp_tool_response(record) for record in records], total=total, page=page, page_size=page_size)

    async def update_mcp_tool_enabled(
        self,
        tool_id: int,
        payload: McpToolEnabledUpdate,
    ) -> McpToolResponse:
        mcp_tool = await self.repository.get_mcp_tool(tool_id)
        if mcp_tool is None or mcp_tool.sync_status != "synced":
            raise self._not_found("MCP 工具不存在。")
        agent_tool = await self.repository.get_agent_tool_by_mcp_tool(mcp_tool_id=tool_id)
        if agent_tool is None:
            raise self._bad_request("MCP 工具尚未完成同步，请先测试 MCP 服务。")
        agent_tool.enabled = payload.enabled
        agent_tool.status = "published" if payload.enabled else "draft"
        await self.db.commit()
        record = await self.repository.get_mcp_tool_record(tool_id)
        if record is None:
            raise self._not_found("MCP 工具不存在。")
        return self._to_mcp_tool_response(record)

    async def list_agent_tools(self, *, team_id: int | None, keyword: str | None, enabled_status: str, lifecycle_status: str, page: int, page_size: int) -> AgentToolListResponse:
        records, total = await self.repository.list_agent_tools(team_id=team_id, keyword=keyword, enabled_status=enabled_status, lifecycle_status=lifecycle_status, page=page, page_size=page_size)
        return AgentToolListResponse(items=[self._to_agent_tool_response(record) for record in records], total=total, page=page, page_size=page_size)

    async def get_agent_tool(self, tool_id: int) -> AgentToolResponse:
        record = await self.repository.get_agent_tool_record(tool_id)
        if record is None:
            raise self._not_found("Agent 工具不存在。")
        return self._to_agent_tool_response(record)

    async def create_agent_tool(self, payload: AgentToolCreate) -> AgentToolResponse:
        mcp_tool = await self.repository.get_mcp_tool(payload.mcp_tool_id)
        if mcp_tool is None:
            raise self._bad_request("MCP 工具不存在，请先同步 MCP 服务。")
        if mcp_tool.sync_status != "synced":
            raise self._bad_request("MCP 工具已从服务发现结果中移除，请重新同步后再操作。")
        existing_mcp_tool = await self.repository.get_agent_tool_by_mcp_tool(mcp_tool_id=payload.mcp_tool_id)
        if existing_mcp_tool is not None:
            raise self._bad_request("该 MCP 工具已经纳入 Agent 工具目录。")
        tool_key = self._normalize_tool_key(payload.tool_key)
        existing = await self.repository.get_agent_tool_by_key(team_id=payload.team_id, tool_key=tool_key)
        if existing is not None:
            raise self._bad_request("同一团队下已存在相同工具 Key。")
        data = payload.model_dump()
        data["tool_key"] = tool_key
        tool = AgentTool(**data, tool_type="mcp", status="draft")
        saved = await self.repository.create_agent_tool(tool)
        record = await self.repository.get_agent_tool_record(saved.id)
        if record is None:
            raise self._not_found("Agent 工具不存在。")
        return self._to_agent_tool_response(record)

    async def update_agent_tool(self, tool_id: int, payload: AgentToolUpdate) -> AgentToolResponse:
        record = await self.repository.get_agent_tool_record(tool_id)
        if record is None:
            raise self._not_found("Agent 工具不存在。")
        mcp_tool = await self.repository.get_mcp_tool(payload.mcp_tool_id)
        if mcp_tool is None:
            raise self._bad_request("MCP 工具不存在，请先同步 MCP 服务。")
        if mcp_tool.sync_status != "synced":
            raise self._bad_request("MCP 工具已从服务发现结果中移除，请重新同步后再操作。")
        existing_mcp_tool = await self.repository.get_agent_tool_by_mcp_tool(mcp_tool_id=payload.mcp_tool_id)
        if existing_mcp_tool is not None and existing_mcp_tool.id != tool_id:
            raise self._bad_request("该 MCP 工具已经纳入 Agent 工具目录。")
        tool_key = self._normalize_tool_key(payload.tool_key)
        existing = await self.repository.get_agent_tool_by_key(team_id=payload.team_id, tool_key=tool_key)
        if existing is not None and existing.id != tool_id:
            raise self._bad_request("同一团队下已存在相同工具 Key。")
        tool = record.tool
        for key, value in payload.model_dump().items():
            setattr(tool, key, value)
        tool.tool_key = tool_key
        if tool.status == "published":
            tool.status = "verified"
        await self.db.commit()
        refreshed = await self.repository.get_agent_tool_record(tool_id)
        if refreshed is None:
            raise self._not_found("Agent 工具不存在。")
        return self._to_agent_tool_response(refreshed)

    async def test_agent_tool(self, tool_id: int, payload: AgentToolTestRequest) -> AgentToolTestResponse:
        record = await self.repository.get_agent_tool_record(tool_id)
        if record is None or record.mcp_tool is None or record.mcp_server is None:
            raise self._not_found("Agent 工具不存在。")
        if record.mcp_tool.sync_status != "synced":
            raise self._bad_request("关联的 MCP 工具已从服务发现结果中移除，无法测试。")
        result = await self.mcp_gateway.call_tool(
            server=record.mcp_server,
            mcp_tool=record.mcp_tool,
            arguments=payload.arguments,
        )
        tool = record.tool
        tool.last_tested_at = utc_now()
        tool.last_test_error = None if result.success else result.message
        tool.status = "verified" if result.success else "error"
        await self.db.commit()
        return AgentToolTestResponse(
            success=result.success,
            status=tool.status,
            message=result.message,
            duration_ms=result.duration_ms,
            data=result.data,
            error_message=result.error.message if result.error else None,
        )

    async def publish_agent_tool(self, tool_id: int) -> AgentToolPublishResponse:
        record = await self.repository.get_agent_tool_record(tool_id)
        if record is None:
            raise self._not_found("Agent 工具不存在。")
        if record.mcp_tool is None or record.mcp_tool.sync_status != "synced":
            raise self._bad_request("关联的 MCP 工具已从服务发现结果中移除，无法发布。")
        record.tool.status = "published"
        record.tool.enabled = True
        await self.db.commit()
        return AgentToolPublishResponse(id=tool_id, status="published", message="Agent 工具已发布。")

    async def unpublish_agent_tool(self, tool_id: int) -> AgentToolPublishResponse:
        record = await self.repository.get_agent_tool_record(tool_id)
        if record is None:
            raise self._not_found("Agent 工具不存在。")
        record.tool.status = "draft"
        await self.db.commit()
        return AgentToolPublishResponse(id=tool_id, status="draft", message="Agent 工具已取消发布。")

    async def delete_agent_tool(self, tool_id: int) -> None:
        record = await self.repository.get_agent_tool_record(tool_id)
        if record is None:
            raise self._not_found("Agent 工具不存在。")
        await self.repository.delete_agent_tool(record.tool)

    async def list_project_app_tool_set_bindings(
        self,
        *,
        project_id: int,
        app_id: int,
    ) -> AgentAppToolSetBindingListResponse:
        app = await self.repository.get_project_app(project_id=project_id, app_id=app_id)
        if app is None:
            raise self._not_found("应用端不存在。")
        records = await self.repository.list_project_app_tool_set_bindings(project_app_id=app.id)
        return AgentAppToolSetBindingListResponse(
            items=[self._to_tool_set_binding_response(record) for record in records]
        )

    async def bind_project_app_tool_set(
        self,
        *,
        project_id: int,
        app_id: int,
        payload: AgentAppToolSetBindingCreate,
    ) -> AgentAppToolSetBindingResponse:
        app = await self.repository.get_project_app(project_id=project_id, app_id=app_id)
        if app is None:
            raise self._not_found("应用端不存在。")
        project_team_id = await self.repository.get_project_app_team_id(project_id=project_id, app_id=app_id)
        server = await self.repository.get_mcp_server(payload.mcp_server_id)
        if server is None or project_team_id is None or server.team_id != project_team_id:
            raise self._bad_request("只能绑定当前项目团队下的 MCP 工具集。")
        binding = await self.repository.get_project_app_tool_set_binding_by_server(
            project_app_id=app.id,
            mcp_server_id=payload.mcp_server_id,
        )
        if binding is None:
            binding = AgentAppToolSetBinding(
                project_app_id=app.id,
                mcp_server_id=payload.mcp_server_id,
            )
        binding.enabled = payload.enabled
        if binding.id is None:
            await self.repository.create_project_app_tool_set_binding(binding)
        else:
            await self.db.commit()
        records = await self.repository.list_project_app_tool_set_bindings(project_app_id=app.id)
        for record in records:
            if record.binding.id == binding.id:
                return self._to_tool_set_binding_response(record)
        raise self._not_found("应用工具集授权不存在。")

    async def unbind_project_app_tool_set(self, *, project_id: int, app_id: int, binding_id: int) -> None:
        app = await self.repository.get_project_app(project_id=project_id, app_id=app_id)
        if app is None:
            raise self._not_found("应用端不存在。")
        binding = await self.repository.get_project_app_tool_set_binding(binding_id)
        if binding is None or binding.project_app_id != app.id:
            raise self._not_found("应用工具集授权不存在。")
        await self.repository.delete_project_app_tool_set_binding(binding)

    async def list_call_logs(
        self,
        *,
        team_id: int | None,
        agent_tool_id: int | None,
        project_app_id: int | None,
        status: str,
        started_at: datetime | None,
        ended_at: datetime | None,
        page: int,
        page_size: int,
    ) -> AgentToolCallLogListResponse:
        records, total = await self.repository.list_call_logs(
            team_id=team_id,
            agent_tool_id=agent_tool_id,
            project_app_id=project_app_id,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            page=page,
            page_size=page_size,
        )
        return AgentToolCallLogListResponse(items=[self._to_log_response(record) for record in records], total=total, page=page, page_size=page_size)
