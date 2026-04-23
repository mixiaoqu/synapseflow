"""Project and project application persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AssistantProfile, KnowledgeBase, Project, ProjectApp, Team


@dataclass(slots=True)
class ProjectRecord:
    project: Project
    team_name: str | None
    app_count: int


@dataclass(slots=True)
class ProjectAppRecord:
    app: ProjectApp
    assistant_name: str | None
    knowledge_base_id: int | None
    knowledge_base_name: str | None


@dataclass(slots=True)
class ProjectAppRuntimeRecord:
    project: Project
    app: ProjectApp
    assistant: AssistantProfile
    knowledge_base_name: str | None


class ProjectRepository:
    """Persist projects and project applications."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def normalize_code(code: str) -> str:
        return (code or "").strip().lower()

    async def list_projects(self, *, team_id: int | None = None) -> list[ProjectRecord]:
        app_count = func.count(ProjectApp.id)
        stmt = (
            select(Project, Team.name, app_count.label("app_count"))
            .join(Team, Team.id == Project.team_id)
            .outerjoin(ProjectApp, ProjectApp.project_id == Project.id)
            .group_by(Project.id, Team.name)
            .order_by(Project.created_at.desc(), Project.id.desc())
        )
        if team_id is not None:
            stmt = stmt.where(Project.team_id == team_id)
        rows = (await self.db.execute(stmt)).all()
        return [
            ProjectRecord(project=project, team_name=team_name, app_count=int(count or 0))
            for project, team_name, count in rows
        ]

    async def get_project_record(self, project_id: int) -> ProjectRecord | None:
        app_count = func.count(ProjectApp.id)
        stmt = (
            select(Project, Team.name, app_count.label("app_count"))
            .join(Team, Team.id == Project.team_id)
            .outerjoin(ProjectApp, ProjectApp.project_id == Project.id)
            .where(Project.id == project_id)
            .group_by(Project.id, Team.name)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        project, team_name, count = row
        return ProjectRecord(project=project, team_name=team_name, app_count=int(count or 0))

    async def get_project(self, project_id: int) -> Project | None:
        return await self.db.get(Project, project_id)

    async def get_project_by_code(self, code: str) -> Project | None:
        stmt = select(Project).where(Project.code == self.normalize_code(code))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def project_code_exists(self, code: str, *, exclude_id: int | None = None) -> bool:
        stmt = select(func.count()).select_from(Project).where(Project.code == self.normalize_code(code))
        if exclude_id is not None:
            stmt = stmt.where(Project.id != exclude_id)
        return bool((await self.db.execute(stmt)).scalar() or 0)

    async def create_project(self, project: Project) -> Project:
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def update_project(self, project: Project) -> Project:
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete_project(self, project: Project) -> None:
        await self.db.delete(project)
        await self.db.commit()

    async def list_apps(self, *, project_id: int) -> list[ProjectAppRecord]:
        stmt = (
            select(
                ProjectApp,
                AssistantProfile.name,
                AssistantProfile.knowledge_base_id,
                KnowledgeBase.name,
            )
            .outerjoin(AssistantProfile, AssistantProfile.id == ProjectApp.default_assistant_id)
            .outerjoin(KnowledgeBase, KnowledgeBase.id == AssistantProfile.knowledge_base_id)
            .where(ProjectApp.project_id == project_id)
            .order_by(ProjectApp.created_at.desc(), ProjectApp.id.desc())
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            ProjectAppRecord(
                app=app,
                assistant_name=assistant_name,
                knowledge_base_id=knowledge_base_id,
                knowledge_base_name=knowledge_base_name,
            )
            for app, assistant_name, knowledge_base_id, knowledge_base_name in rows
        ]

    async def get_app_record(self, app_id: int) -> ProjectAppRecord | None:
        stmt = (
            select(
                ProjectApp,
                AssistantProfile.name,
                AssistantProfile.knowledge_base_id,
                KnowledgeBase.name,
            )
            .outerjoin(AssistantProfile, AssistantProfile.id == ProjectApp.default_assistant_id)
            .outerjoin(KnowledgeBase, KnowledgeBase.id == AssistantProfile.knowledge_base_id)
            .where(ProjectApp.id == app_id)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        app, assistant_name, knowledge_base_id, knowledge_base_name = row
        return ProjectAppRecord(
            app=app,
            assistant_name=assistant_name,
            knowledge_base_id=knowledge_base_id,
            knowledge_base_name=knowledge_base_name,
        )

    async def get_app(self, app_id: int) -> ProjectApp | None:
        return await self.db.get(ProjectApp, app_id)

    async def app_code_exists(
        self,
        *,
        project_id: int,
        code: str,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = (
            select(func.count())
            .select_from(ProjectApp)
            .where(
                ProjectApp.project_id == project_id,
                ProjectApp.code == self.normalize_code(code),
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(ProjectApp.id != exclude_id)
        return bool((await self.db.execute(stmt)).scalar() or 0)

    async def create_app(self, app: ProjectApp) -> ProjectApp:
        self.db.add(app)
        await self.db.commit()
        await self.db.refresh(app)
        return app

    async def update_app(self, app: ProjectApp) -> ProjectApp:
        await self.db.commit()
        await self.db.refresh(app)
        return app

    async def delete_app(self, app: ProjectApp) -> None:
        await self.db.delete(app)
        await self.db.commit()

    async def get_runtime_by_codes(
        self,
        *,
        project_code: str,
        app_code: str,
        active_only: bool = True,
    ) -> ProjectAppRuntimeRecord | None:
        stmt = (
            select(Project, ProjectApp, AssistantProfile, KnowledgeBase.name)
            .join(ProjectApp, ProjectApp.project_id == Project.id)
            .join(AssistantProfile, AssistantProfile.id == ProjectApp.default_assistant_id)
            .outerjoin(KnowledgeBase, KnowledgeBase.id == AssistantProfile.knowledge_base_id)
            .where(
                Project.code == self.normalize_code(project_code),
                ProjectApp.code == self.normalize_code(app_code),
            )
        )
        if active_only:
            stmt = stmt.where(
                Project.is_active.is_(True),
                ProjectApp.is_active.is_(True),
                AssistantProfile.is_active.is_(True),
            )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        project, app, assistant, knowledge_base_name = row
        return ProjectAppRuntimeRecord(
            project=project,
            app=app,
            assistant=assistant,
            knowledge_base_name=knowledge_base_name,
        )

    async def get_runtime_by_app_id(
        self,
        *,
        project_app_id: int,
        active_only: bool = True,
    ) -> ProjectAppRuntimeRecord | None:
        stmt = (
            select(Project, ProjectApp, AssistantProfile, KnowledgeBase.name)
            .join(ProjectApp, ProjectApp.project_id == Project.id)
            .join(AssistantProfile, AssistantProfile.id == ProjectApp.default_assistant_id)
            .outerjoin(KnowledgeBase, KnowledgeBase.id == AssistantProfile.knowledge_base_id)
            .where(ProjectApp.id == project_app_id)
        )
        if active_only:
            stmt = stmt.where(
                Project.is_active.is_(True),
                ProjectApp.is_active.is_(True),
                AssistantProfile.is_active.is_(True),
            )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        project, app, assistant, knowledge_base_name = row
        return ProjectAppRuntimeRecord(
            project=project,
            app=app,
            assistant=assistant,
            knowledge_base_name=knowledge_base_name,
        )
