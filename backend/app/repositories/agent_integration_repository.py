"""Repository for Agent integration data access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentAppToolSetBinding,
    AgentTool,
    AgentToolCallLog,
    McpServer,
    McpTool,
    Project,
    ProjectApp,
    ProjectAppAccessCredential,
    Team,
)


@dataclass(slots=True)
class McpServerRecord:
    server: McpServer
    team_name: str | None
    tool_count: int


@dataclass(slots=True)
class McpToolRecord:
    tool: McpTool
    server_name: str | None
    agent_tool_id: int | None
    agent_tool_status: str | None
    agent_tool_enabled: bool


@dataclass(slots=True)
class AgentToolRecord:
    tool: AgentTool
    team_name: str | None
    mcp_tool: McpTool | None
    mcp_server: McpServer | None


@dataclass(slots=True)
class AgentToolExecutionRecord:
    tool: AgentTool
    mcp_tool: McpTool
    mcp_server: McpServer


@dataclass(slots=True)
class AgentAppToolSetBindingRecord:
    binding: AgentAppToolSetBinding
    mcp_server: McpServer
    tool_count: int
    unavailable_reason: str | None


@dataclass(slots=True)
class AgentToolCallLogRecord:
    log: AgentToolCallLog
    team_name: str | None
    project_app_name: str | None
    mcp_server_name: str | None


class AgentIntegrationRepository:
    """Data access for MCP servers, Agent tools, app bindings and audit logs."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def normalize_key(value: str) -> str:
        return "_".join(str(value or "").strip().lower().replace("-", "_").split())

    @staticmethod
    def _apply_team_filter(stmt: Select[Any], column: Any, team_id: int | None) -> Select[Any]:
        return stmt.where(column == team_id) if team_id else stmt

    @staticmethod
    def _apply_keyword_filter(stmt: Select[Any], keyword: str | None, *columns: Any) -> Select[Any]:
        normalized = str(keyword or "").strip()
        if not normalized:
            return stmt
        pattern = f"%{normalized}%"
        return stmt.where(or_(*(column.ilike(pattern) for column in columns)))

    async def list_mcp_servers(
        self,
        *,
        team_id: int | None,
        keyword: str | None,
        status: str,
        page: int,
        page_size: int,
    ) -> tuple[list[McpServerRecord], int]:
        tool_count_subquery = (
            select(McpTool.mcp_server_id, func.count(McpTool.id).label("tool_count"))
            .where(McpTool.sync_status == "synced")
            .group_by(McpTool.mcp_server_id)
            .subquery()
        )
        base = select(McpServer).join(Team, Team.id == McpServer.team_id)
        base = self._apply_team_filter(base, McpServer.team_id, team_id)
        base = self._apply_keyword_filter(base, keyword, McpServer.name, McpServer.description, McpServer.endpoint_url)
        if status != "all":
            base = base.where(McpServer.status == status)
        total = await self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = (
            base.with_only_columns(McpServer, Team.name, func.coalesce(tool_count_subquery.c.tool_count, 0))
            .outerjoin(tool_count_subquery, tool_count_subquery.c.mcp_server_id == McpServer.id)
            .order_by(McpServer.updated_at.desc(), McpServer.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            McpServerRecord(
                server=row[0],
                team_name=row[1],
                tool_count=int(row[2] or 0),
            )
            for row in rows
        ], int(total)

    async def get_mcp_server(self, server_id: int) -> McpServer | None:
        return await self.db.get(McpServer, server_id)

    async def create_mcp_server(self, server: McpServer) -> McpServer:
        self.db.add(server)
        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def delete_mcp_server(self, server: McpServer) -> None:
        agent_tools = await self.list_agent_tools_for_mcp_server(server_id=server.id)
        for agent_tool in agent_tools:
            await self.db.delete(agent_tool)
        await self.db.flush()
        await self.db.delete(server)
        await self.db.commit()

    async def upsert_mcp_tools(self, *, server_id: int, tools: list[dict[str, Any]]) -> int:
        existing_rows = await self.db.execute(select(McpTool).where(McpTool.mcp_server_id == server_id))
        existing_by_name = {item.raw_name: item for item in existing_rows.scalars().all()}
        discovered_names = {str(item["raw_name"]) for item in tools}
        now = datetime.utcnow()
        for raw_name, tool in existing_by_name.items():
            if raw_name not in discovered_names:
                tool.sync_status = "removed"
        for item in tools:
            raw_name = str(item["raw_name"])
            tool = existing_by_name.get(raw_name)
            if tool is None:
                tool = McpTool(mcp_server_id=server_id, raw_name=raw_name)
                self.db.add(tool)
            tool.raw_description = item.get("raw_description")
            tool.input_schema = item.get("input_schema") or {}
            tool.output_schema = item.get("output_schema") or {}
            tool.schema_hash = str(item.get("schema_hash") or "")
            tool.sync_status = "synced"
            tool.raw_payload = item.get("raw_payload") or {}
            tool.last_synced_at = now
        await self.db.commit()
        return len(tools)

    async def list_mcp_tools(
        self,
        *,
        team_id: int | None,
        server_id: int | None,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[McpToolRecord], int]:
        base = select(McpTool).join(McpServer, McpServer.id == McpTool.mcp_server_id)
        base = base.where(McpTool.sync_status == "synced")
        base = self._apply_team_filter(base, McpServer.team_id, team_id)
        if server_id:
            base = base.where(McpTool.mcp_server_id == server_id)
        base = self._apply_keyword_filter(base, keyword, McpTool.raw_name, McpTool.raw_description)
        total = await self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = (
            base.with_only_columns(McpTool, McpServer.name, AgentTool.id, AgentTool.status, AgentTool.enabled)
            .outerjoin(AgentTool, AgentTool.mcp_tool_id == McpTool.id)
            .order_by(McpTool.updated_at.desc(), McpTool.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            McpToolRecord(
                tool=row[0],
                server_name=row[1],
                agent_tool_id=row[2],
                agent_tool_status=row[3],
                agent_tool_enabled=bool(row[4]),
            )
            for row in rows
        ], int(total)

    async def get_mcp_tool(self, tool_id: int) -> McpTool | None:
        return await self.db.get(McpTool, tool_id)

    async def get_mcp_tool_record(self, tool_id: int) -> McpToolRecord | None:
        stmt = (
            select(McpTool, McpServer.name, AgentTool.id, AgentTool.status, AgentTool.enabled)
            .join(McpServer, McpServer.id == McpTool.mcp_server_id)
            .outerjoin(AgentTool, AgentTool.mcp_tool_id == McpTool.id)
            .where(McpTool.id == tool_id)
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        return McpToolRecord(
            tool=row[0],
            server_name=row[1],
            agent_tool_id=row[2],
            agent_tool_status=row[3],
            agent_tool_enabled=bool(row[4]),
        )

    async def list_synced_mcp_tools_for_server(self, *, server_id: int) -> list[McpTool]:
        stmt = (
            select(McpTool)
            .where(
                McpTool.mcp_server_id == server_id,
                McpTool.sync_status == "synced",
            )
            .order_by(McpTool.id.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_agent_tools_for_mcp_server(self, *, server_id: int) -> list[AgentTool]:
        stmt = (
            select(AgentTool)
            .join(McpTool, McpTool.id == AgentTool.mcp_tool_id)
            .where(McpTool.mcp_server_id == server_id)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_agent_tools(
        self,
        *,
        team_id: int | None,
        keyword: str | None,
        enabled_status: str,
        lifecycle_status: str,
        page: int,
        page_size: int,
    ) -> tuple[list[AgentToolRecord], int]:
        base = (
            select(AgentTool)
            .join(Team, Team.id == AgentTool.team_id)
            .join(McpTool, McpTool.id == AgentTool.mcp_tool_id)
            .where(McpTool.sync_status == "synced")
        )
        base = self._apply_team_filter(base, AgentTool.team_id, team_id)
        base = self._apply_keyword_filter(base, keyword, AgentTool.name, AgentTool.tool_key, AgentTool.description)
        if enabled_status == "enabled":
            base = base.where(AgentTool.enabled.is_(True))
        elif enabled_status == "disabled":
            base = base.where(AgentTool.enabled.is_(False))
        if lifecycle_status != "all":
            base = base.where(AgentTool.status == lifecycle_status)
        total = await self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = (
            base.with_only_columns(AgentTool, Team.name, McpTool, McpServer)
            .join(McpServer, McpServer.id == McpTool.mcp_server_id)
            .order_by(AgentTool.updated_at.desc(), AgentTool.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).all()
        return [AgentToolRecord(tool=row[0], team_name=row[1], mcp_tool=row[2], mcp_server=row[3]) for row in rows], int(total)

    async def get_agent_tool_record(self, tool_id: int) -> AgentToolRecord | None:
        stmt = (
            select(AgentTool, Team.name, McpTool, McpServer)
            .join(Team, Team.id == AgentTool.team_id)
            .join(McpTool, McpTool.id == AgentTool.mcp_tool_id)
            .join(McpServer, McpServer.id == McpTool.mcp_server_id)
            .where(AgentTool.id == tool_id)
        )
        row = (await self.db.execute(stmt)).first()
        return AgentToolRecord(tool=row[0], team_name=row[1], mcp_tool=row[2], mcp_server=row[3]) if row else None

    async def get_agent_tool_by_key(self, *, team_id: int, tool_key: str) -> AgentTool | None:
        stmt = select(AgentTool).where(AgentTool.team_id == team_id, AgentTool.tool_key == tool_key)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_agent_tool_by_mcp_tool(self, *, mcp_tool_id: int) -> AgentTool | None:
        stmt = select(AgentTool).where(AgentTool.mcp_tool_id == mcp_tool_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_agent_tool(self, tool: AgentTool) -> AgentTool:
        self.db.add(tool)
        await self.db.commit()
        await self.db.refresh(tool)
        return tool

    async def delete_agent_tool(self, tool: AgentTool) -> None:
        await self.db.delete(tool)
        await self.db.commit()

    async def get_project_app(self, *, project_id: int, app_id: int) -> ProjectApp | None:
        stmt = select(ProjectApp).join(Project, Project.id == ProjectApp.project_id).where(
            Project.id == project_id,
            ProjectApp.id == app_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_access_credential_by_app(
        self,
        project_app_id: int,
    ) -> ProjectAppAccessCredential | None:
        stmt = select(ProjectAppAccessCredential).where(
            ProjectAppAccessCredential.project_app_id == project_app_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_access_credential_by_client_id(
        self,
        client_id: str,
    ) -> ProjectAppAccessCredential | None:
        stmt = select(ProjectAppAccessCredential).where(
            ProjectAppAccessCredential.client_id == client_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def save_access_credential(
        self,
        credential: ProjectAppAccessCredential,
    ) -> ProjectAppAccessCredential:
        self.db.add(credential)
        await self.db.commit()
        await self.db.refresh(credential)
        return credential

    async def list_project_app_tool_set_bindings(
        self,
        *,
        project_app_id: int,
    ) -> list[AgentAppToolSetBindingRecord]:
        tool_count_subquery = (
            select(McpTool.mcp_server_id, func.count(McpTool.id).label("tool_count"))
            .where(McpTool.sync_status == "synced")
            .group_by(McpTool.mcp_server_id)
            .subquery()
        )
        stmt = (
            select(
                AgentAppToolSetBinding,
                McpServer,
                func.coalesce(tool_count_subquery.c.tool_count, 0),
            )
            .join(McpServer, McpServer.id == AgentAppToolSetBinding.mcp_server_id)
            .outerjoin(tool_count_subquery, tool_count_subquery.c.mcp_server_id == McpServer.id)
            .where(AgentAppToolSetBinding.project_app_id == project_app_id)
            .order_by(AgentAppToolSetBinding.updated_at.desc(), AgentAppToolSetBinding.id.desc())
        )
        rows = (await self.db.execute(stmt)).all()
        records: list[AgentAppToolSetBindingRecord] = []
        for binding, server, tool_count in rows:
            reason = None
            if not binding.enabled:
                reason = "工具集授权已停用"
            elif not server.enabled or server.status != "available":
                reason = "MCP 工具集不可用"
            records.append(
                AgentAppToolSetBindingRecord(
                    binding=binding,
                    mcp_server=server,
                    tool_count=int(tool_count or 0),
                    unavailable_reason=reason,
                )
            )
        return records

    async def get_project_app_tool_set_binding(self, binding_id: int) -> AgentAppToolSetBinding | None:
        return await self.db.get(AgentAppToolSetBinding, binding_id)

    async def get_project_app_tool_set_binding_by_server(
        self,
        *,
        project_app_id: int,
        mcp_server_id: int,
    ) -> AgentAppToolSetBinding | None:
        stmt = select(AgentAppToolSetBinding).where(
            AgentAppToolSetBinding.project_app_id == project_app_id,
            AgentAppToolSetBinding.mcp_server_id == mcp_server_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_project_app_team_id(self, *, project_id: int, app_id: int) -> int | None:
        stmt = (
            select(Project.team_id)
            .join(ProjectApp, ProjectApp.project_id == Project.id)
            .where(Project.id == project_id, ProjectApp.id == app_id)
        )
        value = await self.db.scalar(stmt)
        return int(value) if value is not None else None

    async def create_project_app_tool_set_binding(
        self,
        binding: AgentAppToolSetBinding,
    ) -> AgentAppToolSetBinding:
        self.db.add(binding)
        await self.db.commit()
        await self.db.refresh(binding)
        return binding

    async def delete_project_app_tool_set_binding(self, binding: AgentAppToolSetBinding) -> None:
        await self.db.delete(binding)
        await self.db.commit()

    async def list_available_project_app_tools(self, *, project_app_id: int) -> list[AgentToolExecutionRecord]:
        stmt = (
            select(AgentTool, McpTool, McpServer)
            .join(McpTool, McpTool.id == AgentTool.mcp_tool_id)
            .join(McpServer, McpServer.id == McpTool.mcp_server_id)
            .join(
                AgentAppToolSetBinding,
                AgentAppToolSetBinding.mcp_server_id == McpServer.id,
            )
            .where(
                AgentAppToolSetBinding.project_app_id == project_app_id,
                AgentAppToolSetBinding.enabled.is_(True),
                AgentTool.enabled.is_(True),
                AgentTool.status == "published",
                McpTool.sync_status == "synced",
                McpServer.enabled.is_(True),
                McpServer.status == "available",
            )
            .order_by(AgentTool.name.asc(), AgentTool.id.asc())
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            AgentToolExecutionRecord(
                tool=row[0],
                mcp_tool=row[1],
                mcp_server=row[2],
            )
            for row in rows
        ]

    async def get_available_project_app_tool_by_key(
        self,
        *,
        project_app_id: int,
        tool_key: str,
    ) -> AgentToolExecutionRecord | None:
        stmt = (
            select(AgentTool, McpTool, McpServer)
            .join(McpTool, McpTool.id == AgentTool.mcp_tool_id)
            .join(McpServer, McpServer.id == McpTool.mcp_server_id)
            .join(
                AgentAppToolSetBinding,
                AgentAppToolSetBinding.mcp_server_id == McpServer.id,
            )
            .where(
                AgentAppToolSetBinding.project_app_id == project_app_id,
                AgentAppToolSetBinding.enabled.is_(True),
                AgentTool.tool_key == tool_key,
                AgentTool.enabled.is_(True),
                AgentTool.status == "published",
                McpTool.sync_status == "synced",
                McpServer.enabled.is_(True),
                McpServer.status == "available",
            )
        )
        row = (await self.db.execute(stmt)).first()
        return (
            AgentToolExecutionRecord(
                tool=row[0],
                mcp_tool=row[1],
                mcp_server=row[2],
            )
            if row
            else None
        )

    async def create_call_log(self, log: AgentToolCallLog) -> AgentToolCallLog:
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

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
    ) -> tuple[list[AgentToolCallLogRecord], int]:
        base = select(AgentToolCallLog)
        if team_id:
            base = base.where(AgentToolCallLog.team_id == team_id)
        if agent_tool_id:
            base = base.where(AgentToolCallLog.agent_tool_id == agent_tool_id)
        if project_app_id:
            base = base.where(AgentToolCallLog.project_app_id == project_app_id)
        if status != "all":
            base = base.where(AgentToolCallLog.status == status)
        if started_at:
            base = base.where(AgentToolCallLog.created_at >= started_at)
        if ended_at:
            base = base.where(AgentToolCallLog.created_at <= ended_at)
        total = await self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = (
            base.with_only_columns(AgentToolCallLog, Team.name, ProjectApp.name, McpServer.name)
            .join(Team, Team.id == AgentToolCallLog.team_id)
            .outerjoin(ProjectApp, ProjectApp.id == AgentToolCallLog.project_app_id)
            .outerjoin(McpServer, McpServer.id == AgentToolCallLog.mcp_server_id)
            .order_by(AgentToolCallLog.created_at.desc(), AgentToolCallLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).all()
        return [AgentToolCallLogRecord(log=row[0], team_name=row[1], project_app_name=row[2], mcp_server_name=row[3]) for row in rows], int(total)
