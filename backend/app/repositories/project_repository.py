"""Project and project application persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssistantProfile,
    DocumentCategory,
    KnowledgeBase,
    Product,
    Project,
    ProjectApp,
    Team,
)


@dataclass(slots=True)
class ProjectRecord:
    project: Project
    team_name: str | None
    product_code: str | None
    product_name: str | None
    app_count: int


@dataclass(slots=True)
class ProjectAppRecord:
    app: ProjectApp
    assistant_name: str | None
    knowledge_base_name: str | None = None
    category_name: str | None = None


@dataclass(slots=True)
class ProjectAppRuntimeRecord:
    product: Product
    project: Project
    app: ProjectApp
    assistant: AssistantProfile
    knowledge_base_name: str | None = None
    category_name: str | None = None


class ProjectRepository:
    """Persist projects and project applications."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def normalize_code(code: str) -> str:
        return (code or "").strip().lower()

    async def list_projects(self, *, team_id: int | None = None) -> list[ProjectRecord]:
        return await self.list_projects_page(team_id=team_id, offset=0, limit=None)

    async def count_projects(
        self,
        *,
        team_id: int | None = None,
        product_id: int | None = None,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(Project).join(Product, Product.id == Project.product_id)
        if team_id is not None:
            stmt = stmt.where(Project.team_id == team_id)
        if product_id is not None:
            stmt = stmt.where(Project.product_id == product_id)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    Project.name.ilike(pattern),
                    Project.code.ilike(pattern),
                    Project.description.ilike(pattern),
                    Product.name.ilike(pattern),
                    Product.code.ilike(pattern),
                )
            )
        if is_active is not None:
            stmt = stmt.where(Project.is_active.is_(is_active))
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def list_projects_page(
        self,
        *,
        team_id: int | None = None,
        product_id: int | None = None,
        keyword: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[ProjectRecord]:
        app_count = func.count(ProjectApp.id)
        stmt = (
            select(Project, Team.name, Product.code, Product.name, app_count.label("app_count"))
            .join(Team, Team.id == Project.team_id)
            .join(Product, Product.id == Project.product_id)
            .outerjoin(ProjectApp, ProjectApp.project_id == Project.id)
            .group_by(Project.id, Team.name, Product.code, Product.name)
            .order_by(Project.created_at.desc(), Project.id.desc())
        )
        if team_id is not None:
            stmt = stmt.where(Project.team_id == team_id)
        if product_id is not None:
            stmt = stmt.where(Project.product_id == product_id)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    Project.name.ilike(pattern),
                    Project.code.ilike(pattern),
                    Project.description.ilike(pattern),
                    Product.name.ilike(pattern),
                    Product.code.ilike(pattern),
                )
            )
        if is_active is not None:
            stmt = stmt.where(Project.is_active.is_(is_active))
        if limit is not None:
            stmt = stmt.offset(offset).limit(limit)
        rows = (await self.db.execute(stmt)).all()
        return [
            ProjectRecord(
                project=project,
                team_name=team_name,
                product_code=product_code,
                product_name=product_name,
                app_count=int(count or 0),
            )
            for project, team_name, product_code, product_name, count in rows
        ]

    async def get_project_record(self, project_id: int) -> ProjectRecord | None:
        app_count = func.count(ProjectApp.id)
        stmt = (
            select(Project, Team.name, Product.code, Product.name, app_count.label("app_count"))
            .join(Team, Team.id == Project.team_id)
            .join(Product, Product.id == Project.product_id)
            .outerjoin(ProjectApp, ProjectApp.project_id == Project.id)
            .where(Project.id == project_id)
            .group_by(Project.id, Team.name, Product.code, Product.name)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        project, team_name, product_code, product_name, count = row
        return ProjectRecord(
            project=project,
            team_name=team_name,
            product_code=product_code,
            product_name=product_name,
            app_count=int(count or 0),
        )

    async def get_project(self, project_id: int) -> Project | None:
        return await self.db.get(Project, project_id)

    async def get_projects(self, project_ids: list[int]) -> list[Project]:
        unique_ids = [int(project_id) for project_id in dict.fromkeys(project_ids)]
        if not unique_ids:
            return []
        result = await self.db.execute(select(Project).where(Project.id.in_(unique_ids)))
        rows = list(result.scalars().all())
        order = {project_id: index for index, project_id in enumerate(unique_ids)}
        return sorted(rows, key=lambda project: order.get(int(project.id), len(order)))

    async def get_project_by_code(self, code: str) -> Project | None:
        stmt = select(Project).where(Project.code == self.normalize_code(code))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def project_code_exists(
        self,
        product_id: int,
        code: str,
        *,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = (
            select(func.count())
            .select_from(Project)
            .where(
                Project.product_id == product_id,
                Project.code == self.normalize_code(code),
            )
        )
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

    async def create_project_with_apps(
        self,
        project: Project,
        source_apps: list[ProjectApp],
    ) -> Project:
        self.db.add(project)
        await self.db.flush()
        for source_app in source_apps:
            self.db.add(
                ProjectApp(
                    project_id=project.id,
                    code=source_app.code,
                    name=source_app.name,
                    description=source_app.description,
                    knowledge_base_id=source_app.knowledge_base_id,
                    category_id=source_app.category_id,
                    default_assistant_id=source_app.default_assistant_id,
                    terminal_type=source_app.terminal_type,
                    is_active=source_app.is_active,
                )
            )
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete_project(self, project: Project) -> None:
        await self.db.delete(project)
        await self.db.commit()

    async def count_apps(
        self,
        *,
        project_id: int,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(ProjectApp)
            .outerjoin(AssistantProfile, AssistantProfile.id == ProjectApp.default_assistant_id)
            .outerjoin(KnowledgeBase, KnowledgeBase.id == ProjectApp.knowledge_base_id)
            .outerjoin(DocumentCategory, DocumentCategory.id == ProjectApp.category_id)
            .where(ProjectApp.project_id == project_id)
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    ProjectApp.name.ilike(pattern),
                    ProjectApp.code.ilike(pattern),
                    ProjectApp.description.ilike(pattern),
                    AssistantProfile.name.ilike(pattern),
                    KnowledgeBase.name.ilike(pattern),
                    DocumentCategory.name.ilike(pattern),
                )
            )
        if is_active is not None:
            stmt = stmt.where(ProjectApp.is_active.is_(is_active))
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def list_apps(
        self,
        *,
        project_id: int,
        keyword: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[ProjectAppRecord]:
        stmt = (
            select(ProjectApp, AssistantProfile.name, KnowledgeBase.name, DocumentCategory.name)
            .outerjoin(AssistantProfile, AssistantProfile.id == ProjectApp.default_assistant_id)
            .outerjoin(KnowledgeBase, KnowledgeBase.id == ProjectApp.knowledge_base_id)
            .outerjoin(DocumentCategory, DocumentCategory.id == ProjectApp.category_id)
            .where(ProjectApp.project_id == project_id)
            .order_by(ProjectApp.created_at.desc(), ProjectApp.id.desc())
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    ProjectApp.name.ilike(pattern),
                    ProjectApp.code.ilike(pattern),
                    ProjectApp.description.ilike(pattern),
                    AssistantProfile.name.ilike(pattern),
                    KnowledgeBase.name.ilike(pattern),
                    DocumentCategory.name.ilike(pattern),
                )
            )
        if is_active is not None:
            stmt = stmt.where(ProjectApp.is_active.is_(is_active))
        if limit is not None:
            stmt = stmt.offset(offset).limit(limit)
        rows = (await self.db.execute(stmt)).all()
        return [
            ProjectAppRecord(
                app=app,
                assistant_name=assistant_name,
                knowledge_base_name=knowledge_base_name,
                category_name=category_name,
            )
            for app, assistant_name, knowledge_base_name, category_name in rows
        ]

    async def get_app_record(self, app_id: int) -> ProjectAppRecord | None:
        stmt = (
            select(ProjectApp, AssistantProfile.name, KnowledgeBase.name, DocumentCategory.name)
            .outerjoin(AssistantProfile, AssistantProfile.id == ProjectApp.default_assistant_id)
            .outerjoin(KnowledgeBase, KnowledgeBase.id == ProjectApp.knowledge_base_id)
            .outerjoin(DocumentCategory, DocumentCategory.id == ProjectApp.category_id)
            .where(ProjectApp.id == app_id)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        app, assistant_name, knowledge_base_name, category_name = row
        return ProjectAppRecord(
            app=app,
            assistant_name=assistant_name,
            knowledge_base_name=knowledge_base_name,
            category_name=category_name,
        )

    async def get_app(self, app_id: int) -> ProjectApp | None:
        return await self.db.get(ProjectApp, app_id)

    async def get_apps(self, app_ids: list[int]) -> list[ProjectApp]:
        unique_ids = [int(app_id) for app_id in dict.fromkeys(app_ids)]
        if not unique_ids:
            return []
        result = await self.db.execute(select(ProjectApp).where(ProjectApp.id.in_(unique_ids)))
        rows = list(result.scalars().all())
        order = {app_id: index for index, app_id in enumerate(unique_ids)}
        return sorted(rows, key=lambda app: order.get(int(app.id), len(order)))

    async def list_app_entities(self, *, project_id: int) -> list[ProjectApp]:
        stmt = (
            select(ProjectApp)
            .where(ProjectApp.project_id == project_id)
            .order_by(ProjectApp.created_at.asc(), ProjectApp.id.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

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

    async def create_app(
        self,
        app: ProjectApp,
    ) -> ProjectApp:
        self.db.add(app)
        await self.db.commit()
        await self.db.refresh(app)
        return app

    async def update_app(
        self,
        app: ProjectApp,
    ) -> ProjectApp:
        await self.db.commit()
        await self.db.refresh(app)
        return app

    async def delete_app(self, app: ProjectApp) -> None:
        await self.db.delete(app)
        await self.db.commit()

    async def get_runtime_by_codes(
        self,
        *,
        product_code: str,
        project_code: str,
        app_code: str,
        active_only: bool = True,
    ) -> ProjectAppRuntimeRecord | None:
        stmt = (
            select(
                Product,
                Project,
                ProjectApp,
                AssistantProfile,
                KnowledgeBase.name,
                DocumentCategory.name,
            )
            .join(Project, Project.product_id == Product.id)
            .join(ProjectApp, ProjectApp.project_id == Project.id)
            .join(AssistantProfile, AssistantProfile.id == ProjectApp.default_assistant_id)
            .outerjoin(KnowledgeBase, KnowledgeBase.id == ProjectApp.knowledge_base_id)
            .outerjoin(DocumentCategory, DocumentCategory.id == ProjectApp.category_id)
            .where(
                Product.code == self.normalize_code(product_code),
                Project.code == self.normalize_code(project_code),
                ProjectApp.code == self.normalize_code(app_code),
            )
        )
        if active_only:
            stmt = stmt.where(
                Product.is_active.is_(True),
                Project.is_active.is_(True),
                ProjectApp.is_active.is_(True),
                AssistantProfile.is_active.is_(True),
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        product, project, app, assistant, knowledge_base_name, category_name = row
        return ProjectAppRuntimeRecord(
            product=product,
            project=project,
            app=app,
            assistant=assistant,
            knowledge_base_name=knowledge_base_name,
            category_name=category_name,
        )

    async def get_runtime_by_app_id(
        self,
        *,
        project_app_id: int,
        active_only: bool = True,
    ) -> ProjectAppRuntimeRecord | None:
        stmt = (
            select(
                Product,
                Project,
                ProjectApp,
                AssistantProfile,
                KnowledgeBase.name,
                DocumentCategory.name,
            )
            .join(Project, Project.product_id == Product.id)
            .join(ProjectApp, ProjectApp.project_id == Project.id)
            .join(AssistantProfile, AssistantProfile.id == ProjectApp.default_assistant_id)
            .outerjoin(KnowledgeBase, KnowledgeBase.id == ProjectApp.knowledge_base_id)
            .outerjoin(DocumentCategory, DocumentCategory.id == ProjectApp.category_id)
            .where(ProjectApp.id == project_app_id)
        )
        if active_only:
            stmt = stmt.where(
                Product.is_active.is_(True),
                Project.is_active.is_(True),
                ProjectApp.is_active.is_(True),
                AssistantProfile.is_active.is_(True),
            )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        product, project, app, assistant, knowledge_base_name, category_name = row
        return ProjectAppRuntimeRecord(
            product=product,
            project=project,
            app=app,
            assistant=assistant,
            knowledge_base_name=knowledge_base_name,
            category_name=category_name,
        )
