"""Persistence helpers for business connections, APIs, tools and call logs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BusinessApi,
    BusinessConnection,
    BusinessTool,
    BusinessToolCallLog,
    BusinessToolImplementation,
    Project,
    ProjectApp,
    ProjectAppBusinessToolBinding,
    Team,
)


@dataclass(slots=True)
class BusinessConnectionRecord:
    connection: BusinessConnection
    team_name: str | None
    tool_count: int = 0
    api_count: int = 0


@dataclass(slots=True)
class BusinessApiRecord:
    api: BusinessApi
    team_name: str | None
    connection: BusinessConnection


@dataclass(slots=True)
class BusinessToolImplementationRecord:
    implementation: BusinessToolImplementation
    api: BusinessApi
    connection: BusinessConnection


@dataclass(slots=True)
class BusinessToolRecord:
    tool: BusinessTool
    team_name: str | None
    primary_implementation: BusinessToolImplementationRecord | None
    implementation_count: int = 0


@dataclass(slots=True)
class BusinessToolExecutionRecord:
    tool: BusinessTool
    team_name: str | None
    implementation: BusinessToolImplementation
    api: BusinessApi
    connection: BusinessConnection


@dataclass(slots=True)
class ProjectAppBusinessToolBindingRecord:
    binding: ProjectAppBusinessToolBinding
    tool: BusinessTool
    primary_implementation: BusinessToolImplementationRecord | None


@dataclass(slots=True)
class BusinessToolCallLogRecord:
    log: BusinessToolCallLog
    team_name: str | None
    project_app_name: str | None


class BusinessToolRepository:
    """Persist and discover reusable business tooling resources."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def normalize_key(value: str) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _apply_team_scope(stmt, *, team_id: int | None, team_ids: list[int] | None, column):
        if team_id is not None:
            return stmt.where(column == team_id)
        if team_ids is not None:
            return stmt.where(column.in_(team_ids) if team_ids else false())
        return stmt

    async def _load_tool_primary_implementations(
        self,
        tool_ids: list[int],
    ) -> tuple[dict[int, BusinessToolImplementationRecord], dict[int, int]]:
        if not tool_ids:
            return {}, {}
        rows = (
            await self.db.execute(
                select(BusinessToolImplementation, BusinessApi, BusinessConnection)
                .join(BusinessApi, BusinessApi.id == BusinessToolImplementation.business_api_id)
                .join(BusinessConnection, BusinessConnection.id == BusinessApi.connection_id)
                .where(BusinessToolImplementation.business_tool_id.in_(tool_ids))
                .order_by(
                    BusinessToolImplementation.business_tool_id.asc(),
                    BusinessToolImplementation.enabled.desc(),
                    BusinessToolImplementation.priority.asc(),
                    BusinessToolImplementation.id.asc(),
                )
            )
        ).all()
        primary_by_tool: dict[int, BusinessToolImplementationRecord] = {}
        count_by_tool: dict[int, int] = {}
        for implementation, api, connection in rows:
            tool_id = int(implementation.business_tool_id)
            count_by_tool[tool_id] = count_by_tool.get(tool_id, 0) + 1
            if tool_id not in primary_by_tool:
                primary_by_tool[tool_id] = BusinessToolImplementationRecord(
                    implementation=implementation,
                    api=api,
                    connection=connection,
                )
        return primary_by_tool, count_by_tool

    async def count_connections(
        self,
        *,
        team_id: int | None = None,
        team_ids: list[int] | None = None,
        keyword: str | None = None,
        status: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(BusinessConnection)
        stmt = self._apply_team_scope(
            stmt,
            team_id=team_id,
            team_ids=team_ids,
            column=BusinessConnection.team_id,
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    BusinessConnection.name.ilike(pattern),
                    BusinessConnection.description.ilike(pattern),
                    BusinessConnection.base_url.ilike(pattern),
                )
            )
        if status and status != "all":
            stmt = stmt.where(BusinessConnection.status == status)
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def list_connections_page(
        self,
        *,
        team_id: int | None = None,
        team_ids: list[int] | None = None,
        keyword: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[BusinessConnectionRecord]:
        api_counts = (
            select(BusinessApi.connection_id, func.count(BusinessApi.id).label("api_count"))
            .group_by(BusinessApi.connection_id)
            .subquery()
        )
        tool_counts = (
            select(
                BusinessApi.connection_id,
                func.count(func.distinct(BusinessToolImplementation.business_tool_id)).label("tool_count"),
            )
            .join(BusinessToolImplementation, BusinessToolImplementation.business_api_id == BusinessApi.id)
            .group_by(BusinessApi.connection_id)
            .subquery()
        )
        stmt = (
            select(
                BusinessConnection,
                Team.name,
                func.coalesce(tool_counts.c.tool_count, 0),
                func.coalesce(api_counts.c.api_count, 0),
            )
            .join(Team, Team.id == BusinessConnection.team_id)
            .outerjoin(tool_counts, tool_counts.c.connection_id == BusinessConnection.id)
            .outerjoin(api_counts, api_counts.c.connection_id == BusinessConnection.id)
            .order_by(BusinessConnection.updated_at.desc(), BusinessConnection.id.desc())
        )
        stmt = self._apply_team_scope(
            stmt,
            team_id=team_id,
            team_ids=team_ids,
            column=BusinessConnection.team_id,
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    BusinessConnection.name.ilike(pattern),
                    BusinessConnection.description.ilike(pattern),
                    BusinessConnection.base_url.ilike(pattern),
                )
            )
        if status and status != "all":
            stmt = stmt.where(BusinessConnection.status == status)
        rows = (await self.db.execute(stmt.offset(offset).limit(limit))).all()
        return [
            BusinessConnectionRecord(
                connection=connection,
                team_name=team_name,
                tool_count=int(tool_count or 0),
                api_count=int(api_count or 0),
            )
            for connection, team_name, tool_count, api_count in rows
        ]

    async def get_connection(self, connection_id: int) -> BusinessConnection | None:
        return await self.db.get(BusinessConnection, connection_id)

    async def get_connection_record(self, connection_id: int) -> BusinessConnectionRecord | None:
        api_count = (
            select(func.count(BusinessApi.id))
            .where(BusinessApi.connection_id == BusinessConnection.id)
            .correlate(BusinessConnection)
            .scalar_subquery()
        )
        tool_count = (
            select(func.count(func.distinct(BusinessToolImplementation.business_tool_id)))
            .select_from(BusinessApi)
            .join(BusinessToolImplementation, BusinessToolImplementation.business_api_id == BusinessApi.id)
            .where(BusinessApi.connection_id == BusinessConnection.id)
            .correlate(BusinessConnection)
            .scalar_subquery()
        )
        stmt = (
            select(BusinessConnection, Team.name, tool_count, api_count)
            .join(Team, Team.id == BusinessConnection.team_id)
            .where(BusinessConnection.id == connection_id)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        connection, team_name, resolved_tool_count, resolved_api_count = row
        return BusinessConnectionRecord(
            connection=connection,
            team_name=team_name,
            tool_count=int(resolved_tool_count or 0),
            api_count=int(resolved_api_count or 0),
        )

    async def connection_name_exists(
        self,
        *,
        team_id: int,
        name: str,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = select(func.count()).select_from(BusinessConnection).where(
            BusinessConnection.team_id == team_id,
            func.lower(BusinessConnection.name) == name.strip().lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(BusinessConnection.id != exclude_id)
        return bool((await self.db.execute(stmt)).scalar() or 0)

    async def count_apis_for_connection(self, connection_id: int) -> int:
        stmt = select(func.count()).select_from(BusinessApi).where(
            BusinessApi.connection_id == connection_id
        )
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def save_connection(self, connection: BusinessConnection) -> BusinessConnection:
        self.db.add(connection)
        await self.db.commit()
        await self.db.refresh(connection)
        return connection

    async def delete_connection(self, connection: BusinessConnection) -> None:
        await self.db.delete(connection)
        await self.db.commit()

    async def count_apis(
        self,
        *,
        team_id: int | None = None,
        team_ids: list[int] | None = None,
        keyword: str | None = None,
        enabled: bool | None = None,
        connection_id: int | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(BusinessApi)
        stmt = self._apply_team_scope(
            stmt,
            team_id=team_id,
            team_ids=team_ids,
            column=BusinessApi.team_id,
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    BusinessApi.name.ilike(pattern),
                    BusinessApi.api_key.ilike(pattern),
                    BusinessApi.description.ilike(pattern),
                    BusinessApi.path.ilike(pattern),
                )
            )
        if enabled is not None:
            stmt = stmt.where(BusinessApi.enabled.is_(enabled))
        if connection_id is not None:
            stmt = stmt.where(BusinessApi.connection_id == connection_id)
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def list_apis_page(
        self,
        *,
        team_id: int | None = None,
        team_ids: list[int] | None = None,
        keyword: str | None = None,
        enabled: bool | None = None,
        connection_id: int | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[BusinessApiRecord]:
        stmt = (
            select(BusinessApi, Team.name, BusinessConnection)
            .join(Team, Team.id == BusinessApi.team_id)
            .join(BusinessConnection, BusinessConnection.id == BusinessApi.connection_id)
            .order_by(BusinessApi.updated_at.desc(), BusinessApi.id.desc())
        )
        stmt = self._apply_team_scope(
            stmt,
            team_id=team_id,
            team_ids=team_ids,
            column=BusinessApi.team_id,
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    BusinessApi.name.ilike(pattern),
                    BusinessApi.api_key.ilike(pattern),
                    BusinessApi.description.ilike(pattern),
                    BusinessApi.path.ilike(pattern),
                )
            )
        if enabled is not None:
            stmt = stmt.where(BusinessApi.enabled.is_(enabled))
        if connection_id is not None:
            stmt = stmt.where(BusinessApi.connection_id == connection_id)
        rows = (await self.db.execute(stmt.offset(offset).limit(limit))).all()
        return [
            BusinessApiRecord(api=api, team_name=team_name, connection=connection)
            for api, team_name, connection in rows
        ]

    async def get_api(self, api_id: int) -> BusinessApi | None:
        return await self.db.get(BusinessApi, api_id)

    async def get_api_record(self, api_id: int) -> BusinessApiRecord | None:
        stmt = (
            select(BusinessApi, Team.name, BusinessConnection)
            .join(Team, Team.id == BusinessApi.team_id)
            .join(BusinessConnection, BusinessConnection.id == BusinessApi.connection_id)
            .where(BusinessApi.id == api_id)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        api, team_name, connection = row
        return BusinessApiRecord(api=api, team_name=team_name, connection=connection)

    async def api_key_exists(
        self,
        *,
        team_id: int,
        api_key: str,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = select(func.count()).select_from(BusinessApi).where(
            BusinessApi.team_id == team_id,
            BusinessApi.api_key == self.normalize_key(api_key),
        )
        if exclude_id is not None:
            stmt = stmt.where(BusinessApi.id != exclude_id)
        return bool((await self.db.execute(stmt)).scalar() or 0)

    async def save_api(self, api: BusinessApi) -> BusinessApi:
        self.db.add(api)
        await self.db.commit()
        await self.db.refresh(api)
        return api

    async def delete_api(self, api: BusinessApi) -> None:
        await self.db.delete(api)
        await self.db.commit()

    async def count_implementations_for_api(self, api_id: int) -> int:
        stmt = select(func.count()).select_from(BusinessToolImplementation).where(
            BusinessToolImplementation.business_api_id == api_id
        )
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def count_tools(
        self,
        *,
        team_id: int | None = None,
        team_ids: list[int] | None = None,
        keyword: str | None = None,
        enabled: bool | None = None,
        status: str | None = None,
        connection_id: int | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(BusinessTool)
        stmt = self._apply_team_scope(
            stmt,
            team_id=team_id,
            team_ids=team_ids,
            column=BusinessTool.team_id,
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    BusinessTool.name.ilike(pattern),
                    BusinessTool.tool_key.ilike(pattern),
                    BusinessTool.description.ilike(pattern),
                )
            )
        if enabled is not None:
            stmt = stmt.where(BusinessTool.enabled.is_(enabled))
        if status and status != "all":
            stmt = stmt.where(BusinessTool.status == status)
        if connection_id is not None:
            stmt = stmt.where(
                select(BusinessToolImplementation.id)
                .join(BusinessApi, BusinessApi.id == BusinessToolImplementation.business_api_id)
                .where(
                    BusinessToolImplementation.business_tool_id == BusinessTool.id,
                    BusinessApi.connection_id == connection_id,
                )
                .exists()
            )
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def list_tools_page(
        self,
        *,
        team_id: int | None = None,
        team_ids: list[int] | None = None,
        keyword: str | None = None,
        enabled: bool | None = None,
        status: str | None = None,
        connection_id: int | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[BusinessToolRecord]:
        stmt = (
            select(BusinessTool, Team.name)
            .join(Team, Team.id == BusinessTool.team_id)
            .order_by(BusinessTool.updated_at.desc(), BusinessTool.id.desc())
        )
        stmt = self._apply_team_scope(
            stmt,
            team_id=team_id,
            team_ids=team_ids,
            column=BusinessTool.team_id,
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    BusinessTool.name.ilike(pattern),
                    BusinessTool.tool_key.ilike(pattern),
                    BusinessTool.description.ilike(pattern),
                )
            )
        if enabled is not None:
            stmt = stmt.where(BusinessTool.enabled.is_(enabled))
        if status and status != "all":
            stmt = stmt.where(BusinessTool.status == status)
        if connection_id is not None:
            stmt = stmt.where(
                select(BusinessToolImplementation.id)
                .join(BusinessApi, BusinessApi.id == BusinessToolImplementation.business_api_id)
                .where(
                    BusinessToolImplementation.business_tool_id == BusinessTool.id,
                    BusinessApi.connection_id == connection_id,
                )
                .exists()
            )
        if limit is not None:
            stmt = stmt.offset(offset).limit(limit)
        rows = (await self.db.execute(stmt)).all()
        tool_ids = [tool.id for tool, _team_name in rows]
        primary_by_tool, count_by_tool = await self._load_tool_primary_implementations(tool_ids)
        return [
            BusinessToolRecord(
                tool=tool,
                team_name=team_name,
                primary_implementation=primary_by_tool.get(tool.id),
                implementation_count=count_by_tool.get(tool.id, 0),
            )
            for tool, team_name in rows
        ]

    async def get_tool_record(self, tool_id: int) -> BusinessToolRecord | None:
        stmt = (
            select(BusinessTool, Team.name)
            .join(Team, Team.id == BusinessTool.team_id)
            .where(BusinessTool.id == tool_id)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        tool, team_name = row
        primary_by_tool, count_by_tool = await self._load_tool_primary_implementations([tool.id])
        return BusinessToolRecord(
            tool=tool,
            team_name=team_name,
            primary_implementation=primary_by_tool.get(tool.id),
            implementation_count=count_by_tool.get(tool.id, 0),
        )

    async def get_tool(self, tool_id: int) -> BusinessTool | None:
        return await self.db.get(BusinessTool, tool_id)

    async def tool_key_exists(
        self,
        *,
        team_id: int,
        tool_key: str,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = select(func.count()).select_from(BusinessTool).where(
            BusinessTool.team_id == team_id,
            BusinessTool.tool_key == self.normalize_key(tool_key),
        )
        if exclude_id is not None:
            stmt = stmt.where(BusinessTool.id != exclude_id)
        return bool((await self.db.execute(stmt)).scalar() or 0)

    async def save_tool(self, tool: BusinessTool) -> BusinessTool:
        self.db.add(tool)
        await self.db.commit()
        await self.db.refresh(tool)
        return tool

    async def delete_tool(self, tool: BusinessTool) -> None:
        await self.db.delete(tool)
        await self.db.commit()

    async def count_implementations_for_tool(self, tool_id: int) -> int:
        stmt = select(func.count()).select_from(BusinessToolImplementation).where(
            BusinessToolImplementation.business_tool_id == tool_id
        )
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def list_tool_implementations(
        self,
        *,
        tool_id: int,
    ) -> list[BusinessToolImplementationRecord]:
        rows = (
            await self.db.execute(
                select(BusinessToolImplementation, BusinessApi, BusinessConnection)
                .join(BusinessApi, BusinessApi.id == BusinessToolImplementation.business_api_id)
                .join(BusinessConnection, BusinessConnection.id == BusinessApi.connection_id)
                .where(BusinessToolImplementation.business_tool_id == tool_id)
                .order_by(
                    BusinessToolImplementation.priority.asc(),
                    BusinessToolImplementation.id.asc(),
                )
            )
        ).all()
        return [
            BusinessToolImplementationRecord(
                implementation=implementation,
                api=api,
                connection=connection,
            )
            for implementation, api, connection in rows
        ]

    async def get_tool_implementation(self, implementation_id: int) -> BusinessToolImplementation | None:
        return await self.db.get(BusinessToolImplementation, implementation_id)

    async def get_tool_implementation_record(
        self,
        implementation_id: int,
    ) -> BusinessToolImplementationRecord | None:
        row = (
            await self.db.execute(
                select(BusinessToolImplementation, BusinessApi, BusinessConnection)
                .join(BusinessApi, BusinessApi.id == BusinessToolImplementation.business_api_id)
                .join(BusinessConnection, BusinessConnection.id == BusinessApi.connection_id)
                .where(BusinessToolImplementation.id == implementation_id)
            )
        ).one_or_none()
        if row is None:
            return None
        implementation, api, connection = row
        return BusinessToolImplementationRecord(
            implementation=implementation,
            api=api,
            connection=connection,
        )

    async def save_tool_implementation(
        self,
        implementation: BusinessToolImplementation,
    ) -> BusinessToolImplementation:
        self.db.add(implementation)
        await self.db.commit()
        await self.db.refresh(implementation)
        return implementation

    async def delete_tool_implementation(self, implementation: BusinessToolImplementation) -> None:
        await self.db.delete(implementation)
        await self.db.commit()

    async def list_project_app_bindings(
        self,
        *,
        project_app_id: int,
    ) -> list[ProjectAppBusinessToolBindingRecord]:
        rows = (
            await self.db.execute(
                select(ProjectAppBusinessToolBinding, BusinessTool)
                .join(BusinessTool, BusinessTool.id == ProjectAppBusinessToolBinding.business_tool_id)
                .where(ProjectAppBusinessToolBinding.project_app_id == project_app_id)
                .order_by(BusinessTool.name.asc(), ProjectAppBusinessToolBinding.id.asc())
            )
        ).all()
        tool_ids = [tool.id for _binding, tool in rows]
        primary_by_tool, _count_by_tool = await self._load_tool_primary_implementations(tool_ids)
        return [
            ProjectAppBusinessToolBindingRecord(
                binding=binding,
                tool=tool,
                primary_implementation=primary_by_tool.get(tool.id),
            )
            for binding, tool in rows
        ]

    async def get_project_app_binding(self, binding_id: int) -> ProjectAppBusinessToolBinding | None:
        return await self.db.get(ProjectAppBusinessToolBinding, binding_id)

    async def get_project_app_binding_by_tool(
        self,
        *,
        project_app_id: int,
        business_tool_id: int,
    ) -> ProjectAppBusinessToolBinding | None:
        stmt = select(ProjectAppBusinessToolBinding).where(
            ProjectAppBusinessToolBinding.project_app_id == project_app_id,
            ProjectAppBusinessToolBinding.business_tool_id == business_tool_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def save_project_app_binding(
        self,
        binding: ProjectAppBusinessToolBinding,
    ) -> ProjectAppBusinessToolBinding:
        self.db.add(binding)
        await self.db.commit()
        await self.db.refresh(binding)
        return binding

    async def unbind_project_app_tool(self, binding: ProjectAppBusinessToolBinding) -> None:
        await self.db.delete(binding)
        await self.db.commit()

    async def list_available_project_app_tools(
        self,
        *,
        project_app_id: int,
    ) -> list[BusinessToolExecutionRecord]:
        rows = (
            await self.db.execute(
                select(
                    BusinessTool,
                    Team.name,
                    BusinessToolImplementation,
                    BusinessApi,
                    BusinessConnection,
                )
                .join(
                    ProjectAppBusinessToolBinding,
                    ProjectAppBusinessToolBinding.business_tool_id == BusinessTool.id,
                )
                .join(ProjectApp, ProjectApp.id == ProjectAppBusinessToolBinding.project_app_id)
                .join(Project, Project.id == ProjectApp.project_id)
                .join(Team, Team.id == BusinessTool.team_id)
                .join(
                    BusinessToolImplementation,
                    BusinessToolImplementation.business_tool_id == BusinessTool.id,
                )
                .join(BusinessApi, BusinessApi.id == BusinessToolImplementation.business_api_id)
                .join(BusinessConnection, BusinessConnection.id == BusinessApi.connection_id)
                .where(
                    ProjectAppBusinessToolBinding.project_app_id == project_app_id,
                    ProjectAppBusinessToolBinding.enabled.is_(True),
                    BusinessTool.enabled.is_(True),
                    BusinessTool.status == "published",
                    BusinessTool.team_id == Project.team_id,
                    BusinessToolImplementation.enabled.is_(True),
                    BusinessToolImplementation.status == "published",
                    BusinessApi.enabled.is_(True),
                    BusinessApi.team_id == Project.team_id,
                    BusinessConnection.team_id == Project.team_id,
                    BusinessConnection.enabled.is_(True),
                    BusinessConnection.status == "available",
                )
                .order_by(
                    BusinessTool.name.asc(),
                    BusinessTool.id.asc(),
                    BusinessToolImplementation.priority.asc(),
                    BusinessToolImplementation.id.asc(),
                )
            )
        ).all()
        resolved: dict[int, BusinessToolExecutionRecord] = {}
        for tool, team_name, implementation, api, connection in rows:
            if tool.id in resolved:
                continue
            resolved[tool.id] = BusinessToolExecutionRecord(
                tool=tool,
                team_name=team_name,
                implementation=implementation,
                api=api,
                connection=connection,
            )
        return list(resolved.values())

    async def get_available_project_app_tool_by_key(
        self,
        *,
        project_app_id: int,
        tool_key: str,
    ) -> BusinessToolExecutionRecord | None:
        normalized = self.normalize_key(tool_key)
        records = await self.list_available_project_app_tools(project_app_id=project_app_id)
        return next((record for record in records if record.tool.tool_key == normalized), None)

    async def create_call_log(self, log: BusinessToolCallLog) -> BusinessToolCallLog:
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def count_call_logs(
        self,
        *,
        team_id: int | None = None,
        team_ids: list[int] | None = None,
        tool_id: int | None = None,
        project_app_id: int | None = None,
        status: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(BusinessToolCallLog)
        stmt = self._apply_team_scope(
            stmt,
            team_id=team_id,
            team_ids=team_ids,
            column=BusinessToolCallLog.team_id,
        )
        stmt = self._apply_log_filters(
            stmt,
            tool_id=tool_id,
            project_app_id=project_app_id,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
        )
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def list_call_logs_page(
        self,
        *,
        team_id: int | None = None,
        team_ids: list[int] | None = None,
        tool_id: int | None = None,
        project_app_id: int | None = None,
        status: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[BusinessToolCallLogRecord]:
        stmt = (
            select(BusinessToolCallLog, Team.name, ProjectApp.name)
            .join(Team, Team.id == BusinessToolCallLog.team_id)
            .outerjoin(ProjectApp, ProjectApp.id == BusinessToolCallLog.project_app_id)
        )
        stmt = self._apply_team_scope(
            stmt,
            team_id=team_id,
            team_ids=team_ids,
            column=BusinessToolCallLog.team_id,
        )
        stmt = self._apply_log_filters(
            stmt,
            tool_id=tool_id,
            project_app_id=project_app_id,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
        )
        stmt = stmt.order_by(BusinessToolCallLog.created_at.desc(), BusinessToolCallLog.id.desc())
        rows = (await self.db.execute(stmt.offset(offset).limit(limit))).all()
        return [
            BusinessToolCallLogRecord(log=log, team_name=team_name, project_app_name=app_name)
            for log, team_name, app_name in rows
        ]

    @staticmethod
    def _apply_log_filters(
        stmt,
        *,
        tool_id: int | None,
        project_app_id: int | None,
        status: str | None,
        started_at: datetime | None,
        ended_at: datetime | None,
    ):
        if tool_id is not None:
            stmt = stmt.where(BusinessToolCallLog.business_tool_id == tool_id)
        if project_app_id is not None:
            stmt = stmt.where(BusinessToolCallLog.project_app_id == project_app_id)
        if status and status != "all":
            stmt = stmt.where(BusinessToolCallLog.status == status)
        if started_at is not None:
            stmt = stmt.where(BusinessToolCallLog.created_at >= started_at)
        if ended_at is not None:
            stmt = stmt.where(BusinessToolCallLog.created_at <= ended_at)
        return stmt
