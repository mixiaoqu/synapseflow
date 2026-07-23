"""Data access for tool providers, governed tools, grants and invocations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentAppToolGrant,
    AgentTool,
    AgentToolInvocation,
    Project,
    ProjectApp,
    Team,
    ToolProvider,
)


@dataclass(slots=True)
class ToolProviderRecord:
    provider: ToolProvider
    team_name: str | None
    tool_count: int


@dataclass(slots=True)
class AgentToolRecord:
    tool: AgentTool
    provider: ToolProvider
    team_name: str | None


@dataclass(slots=True)
class AgentToolExecutionRecord:
    tool: AgentTool
    provider: ToolProvider


@dataclass(slots=True)
class AgentToolGrantRecord:
    grant: AgentAppToolGrant
    tool: AgentTool
    provider: ToolProvider


@dataclass(slots=True)
class AgentToolInvocationRecord:
    invocation: AgentToolInvocation
    team_name: str | None
    project_app_name: str | None
    provider_name: str | None


class AgentToolRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def normalize_key(value: str) -> str:
        return "_".join(str(value or "").strip().lower().replace("-", "_").split())

    @staticmethod
    def _team_filter(stmt: Select[Any], column: Any, team_id: int | None) -> Select[Any]:
        return stmt.where(column == team_id) if team_id else stmt

    @staticmethod
    def _keyword_filter(stmt: Select[Any], keyword: str | None, *columns: Any) -> Select[Any]:
        normalized = str(keyword or "").strip()
        if not normalized:
            return stmt
        pattern = f"%{normalized}%"
        return stmt.where(or_(*(column.ilike(pattern) for column in columns)))

    async def list_providers(
        self,
        *,
        team_id: int | None,
        keyword: str | None,
        health_status: str,
        page: int,
        page_size: int,
    ) -> tuple[list[ToolProviderRecord], int]:
        counts = (
            select(AgentTool.provider_id, func.count(AgentTool.id).label("tool_count"))
            .where(AgentTool.sync_status == "active")
            .group_by(AgentTool.provider_id)
            .subquery()
        )
        base = select(ToolProvider).join(Team, Team.id == ToolProvider.team_id)
        base = self._team_filter(base, ToolProvider.team_id, team_id)
        base = self._keyword_filter(
            base,
            keyword,
            ToolProvider.code,
            ToolProvider.name,
            ToolProvider.description,
            ToolProvider.base_url,
        )
        if health_status != "all":
            base = base.where(ToolProvider.health_status == health_status)
        total = await self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = (
            base.with_only_columns(ToolProvider, Team.name, func.coalesce(counts.c.tool_count, 0))
            .outerjoin(counts, counts.c.provider_id == ToolProvider.id)
            .order_by(ToolProvider.updated_at.desc(), ToolProvider.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            ToolProviderRecord(provider=row[0], team_name=row[1], tool_count=int(row[2] or 0))
            for row in rows
        ], int(total)

    async def get_provider(self, provider_id: int) -> ToolProvider | None:
        return await self.db.get(ToolProvider, provider_id)

    async def get_provider_by_code(self, *, team_id: int, code: str) -> ToolProvider | None:
        stmt = select(ToolProvider).where(
            ToolProvider.team_id == team_id,
            ToolProvider.code == code,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def save_provider(self, provider: ToolProvider) -> ToolProvider:
        self.db.add(provider)
        await self.db.commit()
        await self.db.refresh(provider)
        return provider

    async def delete_provider(self, provider: ToolProvider) -> None:
        await self.db.delete(provider)
        await self.db.commit()

    async def list_tools_for_provider(self, provider_id: int) -> list[AgentTool]:
        stmt = select(AgentTool).where(AgentTool.provider_id == provider_id).order_by(AgentTool.id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def save_tools(self, tools: list[AgentTool]) -> None:
        self.db.add_all(tools)
        await self.db.commit()

    async def list_tools(
        self,
        *,
        team_id: int | None,
        provider_id: int | None,
        keyword: str | None,
        publish_status: str,
        sync_status: str,
        page: int,
        page_size: int,
    ) -> tuple[list[AgentToolRecord], int]:
        base = (
            select(AgentTool)
            .join(ToolProvider, ToolProvider.id == AgentTool.provider_id)
            .join(Team, Team.id == AgentTool.team_id)
        )
        base = self._team_filter(base, AgentTool.team_id, team_id)
        if provider_id:
            base = base.where(AgentTool.provider_id == provider_id)
        if publish_status != "all":
            base = base.where(AgentTool.publish_status == publish_status)
        if sync_status != "all":
            base = base.where(AgentTool.sync_status == sync_status)
        base = self._keyword_filter(
            base,
            keyword,
            AgentTool.name,
            AgentTool.tool_key,
            AgentTool.external_name,
            AgentTool.external_description,
        )
        total = await self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = (
            base.with_only_columns(AgentTool, ToolProvider, Team.name)
            .order_by(AgentTool.updated_at.desc(), AgentTool.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).all()
        return [AgentToolRecord(tool=row[0], provider=row[1], team_name=row[2]) for row in rows], int(total)

    async def get_tool_record(self, tool_id: int) -> AgentToolRecord | None:
        stmt = (
            select(AgentTool, ToolProvider, Team.name)
            .join(ToolProvider, ToolProvider.id == AgentTool.provider_id)
            .join(Team, Team.id == AgentTool.team_id)
            .where(AgentTool.id == tool_id)
        )
        row = (await self.db.execute(stmt)).first()
        return AgentToolRecord(tool=row[0], provider=row[1], team_name=row[2]) if row else None

    async def get_tool_by_key(self, *, team_id: int, tool_key: str) -> AgentTool | None:
        stmt = select(AgentTool).where(AgentTool.team_id == team_id, AgentTool.tool_key == tool_key)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def save_tool(self, tool: AgentTool) -> AgentTool:
        self.db.add(tool)
        await self.db.commit()
        await self.db.refresh(tool)
        return tool

    async def get_project_app(self, *, project_id: int, app_id: int) -> ProjectApp | None:
        stmt = (
            select(ProjectApp)
            .join(Project, Project.id == ProjectApp.project_id)
            .where(Project.id == project_id, ProjectApp.id == app_id)
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

    async def list_grants(self, *, project_app_id: int) -> list[AgentToolGrantRecord]:
        stmt = (
            select(AgentAppToolGrant, AgentTool, ToolProvider)
            .join(AgentTool, AgentTool.id == AgentAppToolGrant.agent_tool_id)
            .join(ToolProvider, ToolProvider.id == AgentTool.provider_id)
            .where(AgentAppToolGrant.project_app_id == project_app_id)
            .order_by(ToolProvider.name, AgentTool.name)
        )
        rows = (await self.db.execute(stmt)).all()
        return [AgentToolGrantRecord(grant=row[0], tool=row[1], provider=row[2]) for row in rows]

    async def get_grant(self, grant_id: int) -> AgentAppToolGrant | None:
        return await self.db.get(AgentAppToolGrant, grant_id)

    async def get_grant_by_tool(self, *, project_app_id: int, agent_tool_id: int) -> AgentAppToolGrant | None:
        stmt = select(AgentAppToolGrant).where(
            AgentAppToolGrant.project_app_id == project_app_id,
            AgentAppToolGrant.agent_tool_id == agent_tool_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def save_grant(self, grant: AgentAppToolGrant) -> AgentAppToolGrant:
        self.db.add(grant)
        await self.db.commit()
        await self.db.refresh(grant)
        return grant

    async def delete_grant(self, grant: AgentAppToolGrant) -> None:
        await self.db.delete(grant)
        await self.db.commit()

    async def list_available_tools(self, *, project_app_id: int) -> list[AgentToolExecutionRecord]:
        stmt = (
            select(AgentTool, ToolProvider)
            .join(ToolProvider, ToolProvider.id == AgentTool.provider_id)
            .join(AgentAppToolGrant, AgentAppToolGrant.agent_tool_id == AgentTool.id)
            .where(
                AgentAppToolGrant.project_app_id == project_app_id,
                AgentTool.sync_status == "active",
                AgentTool.publish_status == "published",
                AgentTool.schema_hash == AgentTool.approved_schema_hash,
                ToolProvider.enabled.is_(True),
            )
            .order_by(AgentTool.name, AgentTool.id)
        )
        rows = (await self.db.execute(stmt)).all()
        return [AgentToolExecutionRecord(tool=row[0], provider=row[1]) for row in rows]

    async def get_available_tool(
        self,
        *,
        project_app_id: int,
        tool_key: str,
    ) -> AgentToolExecutionRecord | None:
        stmt = (
            select(AgentTool, ToolProvider)
            .join(ToolProvider, ToolProvider.id == AgentTool.provider_id)
            .join(AgentAppToolGrant, AgentAppToolGrant.agent_tool_id == AgentTool.id)
            .where(
                AgentAppToolGrant.project_app_id == project_app_id,
                AgentAppToolGrant.agent_tool_id == AgentTool.id,
                AgentTool.tool_key == tool_key,
                AgentTool.sync_status == "active",
                AgentTool.publish_status == "published",
                AgentTool.schema_hash == AgentTool.approved_schema_hash,
                ToolProvider.enabled.is_(True),
            )
        )
        row = (await self.db.execute(stmt)).first()
        return AgentToolExecutionRecord(tool=row[0], provider=row[1]) if row else None

    async def create_invocation(self, invocation: AgentToolInvocation) -> AgentToolInvocation:
        self.db.add(invocation)
        await self.db.commit()
        await self.db.refresh(invocation)
        return invocation

    async def list_invocations(
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
    ) -> tuple[list[AgentToolInvocationRecord], int]:
        base = select(AgentToolInvocation)
        if team_id:
            base = base.where(AgentToolInvocation.team_id == team_id)
        if agent_tool_id:
            base = base.where(AgentToolInvocation.agent_tool_id == agent_tool_id)
        if project_app_id:
            base = base.where(AgentToolInvocation.project_app_id == project_app_id)
        if status != "all":
            base = base.where(AgentToolInvocation.status == status)
        if started_at:
            base = base.where(AgentToolInvocation.created_at >= started_at)
        if ended_at:
            base = base.where(AgentToolInvocation.created_at <= ended_at)
        total = await self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = (
            base.with_only_columns(AgentToolInvocation, Team.name, ProjectApp.name, ToolProvider.name)
            .join(Team, Team.id == AgentToolInvocation.team_id)
            .outerjoin(ProjectApp, ProjectApp.id == AgentToolInvocation.project_app_id)
            .outerjoin(ToolProvider, ToolProvider.id == AgentToolInvocation.provider_id)
            .order_by(AgentToolInvocation.created_at.desc(), AgentToolInvocation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            AgentToolInvocationRecord(
                invocation=row[0],
                team_name=row[1],
                project_app_name=row[2],
                provider_name=row[3],
            )
            for row in rows
        ], int(total)
