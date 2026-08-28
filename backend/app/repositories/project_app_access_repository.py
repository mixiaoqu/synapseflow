"""Data access for project application integration credentials."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, ProjectApp, ProjectAppAccessCredential


class ProjectAppAccessRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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

    async def get_by_app(self, project_app_id: int) -> ProjectAppAccessCredential | None:
        stmt = select(ProjectAppAccessCredential).where(
            ProjectAppAccessCredential.project_app_id == project_app_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_client_id(self, client_id: str) -> ProjectAppAccessCredential | None:
        stmt = select(ProjectAppAccessCredential).where(
            ProjectAppAccessCredential.client_id == client_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def save(self, credential: ProjectAppAccessCredential) -> ProjectAppAccessCredential:
        self.db.add(credential)
        await self.db.commit()
        await self.db.refresh(credential)
        return credential

