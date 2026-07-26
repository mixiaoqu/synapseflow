"""Project and project application application service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.permission_service import PermissionService
from app.core.authz import PERMISSION_MANAGE_PROJECT, PERMISSION_VIEW_TEAM_RESOURCE
from app.db.models import AssistantProfile, DocumentCategory, Product, Project, ProjectApp, User
from app.models.schemas.project import (
    ProjectAppBulkActionRequest,
    ProjectAppBulkActionResponse,
    ProjectAppCreate,
    ProjectAppListResponse,
    ProjectAppResponse,
    ProjectAppUpdate,
    ProjectBulkActionRequest,
    ProjectBulkActionResponse,
    ProjectCopy,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.repositories.product_repository import ProductRepository
from app.repositories.project_repository import (
    ProjectAppRecord,
    ProjectAppRuntimeRecord,
    ProjectRecord,
    ProjectRepository,
)


class ProjectService:
    def __init__(self, db: AsyncSession, *, user_id: int, user: User | None = None):
        self.db = db
        self.user_id = user_id
        self.user = user
        self.repository = ProjectRepository(db)
        self.product_repository = ProductRepository(db)
        self.permission_service = PermissionService(db)

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None

    @staticmethod
    def _normalize_code(value: str) -> str:
        code = ProjectRepository.normalize_code(value)
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        return code

    @staticmethod
    def _resolve_status_filter(status: str | None) -> bool | None:
        if status == "active":
            return True
        if status == "inactive":
            return False
        return None

    @staticmethod
    def _to_project_response(record: ProjectRecord) -> ProjectResponse:
        project = record.project
        return ProjectResponse(
            id=project.id,
            team_id=project.team_id,
            team_name=record.team_name,
            product_id=project.product_id,
            product_code=record.product_code,
            product_name=record.product_name,
            code=project.code,
            name=project.name,
            description=project.description,
            is_active=project.is_active,
            app_count=record.app_count,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    @staticmethod
    def _to_app_response(record: ProjectAppRecord) -> ProjectAppResponse:
        app = record.app
        return ProjectAppResponse(
            id=app.id,
            project_id=app.project_id,
            code=app.code,
            name=app.name,
            description=app.description,
            knowledge_base_id=app.knowledge_base_id,
            knowledge_base_name=record.knowledge_base_name,
            category_id=app.category_id,
            category_name=record.category_name,
            default_assistant_id=app.default_assistant_id,
            default_assistant_name=record.assistant_name,
            widget_version=app.widget_version,
            terminal_type=app.terminal_type,
            is_active=app.is_active,
            created_at=app.created_at,
            updated_at=app.updated_at,
        )

    async def _ensure_team_permission(
        self,
        team_id: int,
        permission: str = PERMISSION_VIEW_TEAM_RESOURCE,
    ) -> None:
        if self.user is None:
            raise HTTPException(status_code=403, detail="Team access denied")
        if permission == PERMISSION_VIEW_TEAM_RESOURCE:
            allowed = await self.permission_service.can_access_team(self.user, team_id)
        else:
            allowed = await self.permission_service.has_team_permission(
                self.user, team_id, permission
            )
        if not allowed:
            raise HTTPException(status_code=403, detail="Team access denied")

    async def _get_product_for_project(self, *, product_id: int, team_id: int) -> Product:
        product = await self.product_repository.get_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        if product.team_id != team_id:
            raise HTTPException(status_code=400, detail="Product does not belong to the project team")
        return product

    async def _get_assistant_for_project(
        self,
        *,
        project: Project,
        assistant_id: int | None,
    ) -> AssistantProfile | None:
        if assistant_id is None:
            return None
        assistant = await self.db.get(AssistantProfile, assistant_id)
        if assistant is None:
            raise HTTPException(status_code=404, detail="Assistant not found")
        if assistant.team_id != project.team_id:
            raise HTTPException(
                status_code=400,
                detail="Assistant does not belong to the project team",
            )
        return assistant

    async def _validate_knowledge_base_id(
        self,
        *,
        project: Project,
        knowledge_base_id: int | None,
    ) -> int | None:
        from app.repositories.knowledge_base_repository import KnowledgeBaseRepository

        if knowledge_base_id is None:
            return None
        kb_repository = KnowledgeBaseRepository(self.db, user_id=self.user_id, user=self.user)
        resolved_knowledge_base_id = int(knowledge_base_id)
        knowledge_base = await kb_repository.get_by_id(resolved_knowledge_base_id)
        if knowledge_base is None:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        if not getattr(knowledge_base, "is_active", True):
            raise HTTPException(
                status_code=400,
                detail=f"Knowledge base '{knowledge_base.name}' is disabled",
            )
        if knowledge_base.team_id != project.team_id:
            raise HTTPException(
                status_code=400,
                detail="Knowledge base does not belong to the project team",
            )
        return resolved_knowledge_base_id

    async def _validate_category_id(
        self,
        *,
        knowledge_base_id: int | None,
        category_id: int | None,
    ) -> int | None:
        if category_id is None:
            return None
        if knowledge_base_id is None:
            raise HTTPException(
                status_code=400,
                detail="Document category requires a selected knowledge base",
            )
        category = await self.db.get(DocumentCategory, int(category_id))
        if category is None:
            raise HTTPException(status_code=404, detail="Document category not found")
        if category.knowledge_base_id != knowledge_base_id:
            raise HTTPException(
                status_code=400,
                detail="Document category does not belong to the selected knowledge base",
            )
        return int(category_id)

    async def list_projects(self, *, team_id: int | None = None) -> list[ProjectResponse]:
        if team_id is not None:
            await self._ensure_team_permission(team_id)
        records = await self.repository.list_projects(team_id=team_id)
        return [self._to_project_response(record) for record in records]

    async def list_projects_page(
        self,
        *,
        team_id: int | None = None,
        product_id: int | None = None,
        keyword: str | None = None,
        status: str = "all",
        page: int = 1,
        page_size: int = 10,
    ) -> ProjectListResponse:
        if team_id is not None:
            await self._ensure_team_permission(team_id)
        normalized_page = max(1, int(page))
        normalized_page_size = min(100, max(1, int(page_size)))
        is_active = self._resolve_status_filter(status)
        total = await self.repository.count_projects(
            team_id=team_id,
            product_id=product_id,
            keyword=keyword,
            is_active=is_active,
        )
        records = await self.repository.list_projects_page(
            team_id=team_id,
            product_id=product_id,
            keyword=keyword,
            is_active=is_active,
            offset=(normalized_page - 1) * normalized_page_size,
            limit=normalized_page_size,
        )
        return ProjectListResponse(
            items=[self._to_project_response(record) for record in records],
            total=total,
            page=normalized_page,
            page_size=normalized_page_size,
        )

    async def get_project(self, project_id: int) -> ProjectResponse:
        record = await self.repository.get_project_record(project_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(record.project.team_id)
        return self._to_project_response(record)

    async def create_project(self, payload: ProjectCreate) -> ProjectResponse:
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        await self._get_product_for_project(product_id=payload.product_id, team_id=payload.team_id)
        code = self._normalize_code(payload.code)
        if await self.repository.project_code_exists(payload.product_id, code):
            raise HTTPException(status_code=400, detail="Project code already exists")
        project = Project(
            team_id=payload.team_id,
            product_id=payload.product_id,
            code=code,
            name=payload.name.strip(),
            description=self._normalize_optional_text(payload.description),
            is_active=payload.is_active,
        )
        await self.repository.create_project(project)
        record = await self.repository.get_project_record(project.id)
        if record is None:
            raise HTTPException(status_code=500, detail="Project creation failed")
        return self._to_project_response(record)

    async def update_project(self, project_id: int, payload: ProjectUpdate) -> ProjectResponse:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id, PERMISSION_MANAGE_PROJECT)
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        await self._get_product_for_project(product_id=payload.product_id, team_id=payload.team_id)

        code = self._normalize_code(payload.code)
        if await self.repository.project_code_exists(
            payload.product_id,
            code,
            exclude_id=project_id,
        ):
            raise HTTPException(status_code=400, detail="Project code already exists")

        project.team_id = payload.team_id
        project.product_id = payload.product_id
        project.code = code
        project.name = payload.name.strip()
        project.description = self._normalize_optional_text(payload.description)
        project.is_active = payload.is_active
        await self.repository.update_project(project)
        record = await self.repository.get_project_record(project.id)
        if record is None:
            raise HTTPException(status_code=500, detail="Project update failed")
        return self._to_project_response(record)

    async def delete_project(self, project_id: int) -> None:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id, PERMISSION_MANAGE_PROJECT)
        await self.repository.delete_project(project)

    async def bulk_action_projects(
        self,
        payload: ProjectBulkActionRequest,
    ) -> ProjectBulkActionResponse:
        normalized_ids = [project_id for project_id in payload.project_ids if project_id > 0]
        if not normalized_ids:
            raise HTTPException(status_code=400, detail="Project ids are required")
        project_ids = list(dict.fromkeys(normalized_ids))

        projects = await self.repository.get_projects(project_ids)
        if len(projects) != len(project_ids):
            raise HTTPException(status_code=404, detail="One or more projects were not found")
        if not await self.permission_service.has_all_team_permissions(
            self.user,
            [project.team_id for project in projects],
            PERMISSION_MANAGE_PROJECT,
        ):
            raise HTTPException(status_code=403, detail="Team permission denied")

        if payload.action == "enable":
            for project in projects:
                project.is_active = True
        elif payload.action == "disable":
            for project in projects:
                project.is_active = False
        else:
            for project in projects:
                await self.db.delete(project)

        await self.db.commit()
        return ProjectBulkActionResponse(
            action=payload.action,
            affected_ids=project_ids,
            affected_count=len(project_ids),
        )

    async def copy_project(self, *, project_id: int, payload: ProjectCopy) -> ProjectResponse:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id, PERMISSION_MANAGE_PROJECT)

        code = self._normalize_code(payload.code)
        if await self.repository.project_code_exists(project.product_id, code):
            raise HTTPException(status_code=400, detail="Project code already exists")

        source_apps = await self.repository.list_app_entities(project_id=project_id)
        copied_project = Project(
            team_id=project.team_id,
            product_id=project.product_id,
            code=code,
            name=payload.name.strip(),
            description=project.description,
            is_active=payload.is_active,
        )
        await self.repository.create_project_with_apps(copied_project, source_apps)
        record = await self.repository.get_project_record(copied_project.id)
        if record is None:
            raise HTTPException(status_code=500, detail="Project copy failed")
        return self._to_project_response(record)

    async def list_apps(self, *, project_id: int) -> list[ProjectAppResponse]:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id)
        records = await self.repository.list_apps(project_id=project_id)
        return [self._to_app_response(record) for record in records]

    async def list_apps_page(
        self,
        *,
        project_id: int,
        keyword: str | None = None,
        status: str = "all",
        page: int,
        page_size: int,
    ) -> ProjectAppListResponse:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id)
        normalized_page = max(1, page)
        normalized_page_size = min(100, max(1, page_size))
        is_active = self._resolve_status_filter(status)
        total = await self.repository.count_apps(
            project_id=project_id,
            keyword=keyword,
            is_active=is_active,
        )
        records = await self.repository.list_apps(
            project_id=project_id,
            keyword=keyword,
            is_active=is_active,
            offset=(normalized_page - 1) * normalized_page_size,
            limit=normalized_page_size,
        )
        return ProjectAppListResponse(
            items=[self._to_app_response(record) for record in records],
            total=total,
            page=normalized_page,
            page_size=normalized_page_size,
        )

    async def get_app(self, *, project_id: int, app_id: int) -> ProjectAppResponse:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id)
        record = await self.repository.get_app_record(app_id)
        if record is None or record.app.project_id != project_id:
            raise HTTPException(status_code=404, detail="Project app not found")
        return self._to_app_response(record)

    async def get_app_runtime(
        self,
        *,
        project_id: int,
        app_id: int,
        active_only: bool = True,
    ) -> ProjectAppRuntimeRecord:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id)
        runtime = await self.repository.get_runtime_by_app_id(
            project_app_id=app_id,
            active_only=active_only,
        )
        if runtime is None or runtime.project.id != project_id:
            raise HTTPException(status_code=404, detail="Active project application not found")
        return runtime

    async def create_app(
        self,
        *,
        project_id: int,
        payload: ProjectAppCreate,
    ) -> ProjectAppResponse:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id, PERMISSION_MANAGE_PROJECT)
        code = self._normalize_code(payload.code)
        if await self.repository.app_code_exists(project_id=project_id, code=code):
            raise HTTPException(status_code=400, detail="Project app code already exists")
        await self._get_assistant_for_project(
            project=project,
            assistant_id=payload.default_assistant_id,
        )
        normalized_knowledge_base_id = await self._validate_knowledge_base_id(
            project=project,
            knowledge_base_id=payload.knowledge_base_id,
        )
        normalized_category_id = await self._validate_category_id(
            knowledge_base_id=normalized_knowledge_base_id,
            category_id=payload.category_id,
        )
        app = ProjectApp(
            project_id=project_id,
            code=code,
            name=payload.name.strip(),
            description=self._normalize_optional_text(payload.description),
            knowledge_base_id=normalized_knowledge_base_id,
            category_id=normalized_category_id,
            default_assistant_id=payload.default_assistant_id,
            widget_version=payload.widget_version,
            terminal_type=payload.terminal_type,
            is_active=payload.is_active,
        )
        await self.repository.create_app(app)
        record = await self.repository.get_app_record(app.id)
        if record is None:
            raise HTTPException(status_code=500, detail="Project app creation failed")
        return self._to_app_response(record)

    async def update_app(
        self,
        *,
        project_id: int,
        app_id: int,
        payload: ProjectAppUpdate,
    ) -> ProjectAppResponse:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id, PERMISSION_MANAGE_PROJECT)
        app = await self.repository.get_app(app_id)
        if app is None or app.project_id != project_id:
            raise HTTPException(status_code=404, detail="Project app not found")

        code = self._normalize_code(payload.code)
        if await self.repository.app_code_exists(
            project_id=project_id,
            code=code,
            exclude_id=app_id,
        ):
            raise HTTPException(status_code=400, detail="Project app code already exists")
        await self._get_assistant_for_project(
            project=project,
            assistant_id=payload.default_assistant_id,
        )
        normalized_knowledge_base_id = await self._validate_knowledge_base_id(
            project=project,
            knowledge_base_id=payload.knowledge_base_id,
        )
        normalized_category_id = await self._validate_category_id(
            knowledge_base_id=normalized_knowledge_base_id,
            category_id=payload.category_id,
        )
        app.code = code
        app.name = payload.name.strip()
        app.description = self._normalize_optional_text(payload.description)
        app.knowledge_base_id = normalized_knowledge_base_id
        app.category_id = normalized_category_id
        app.default_assistant_id = payload.default_assistant_id
        app.widget_version = payload.widget_version
        app.terminal_type = payload.terminal_type
        app.is_active = payload.is_active
        await self.repository.update_app(app)
        record = await self.repository.get_app_record(app.id)
        if record is None:
            raise HTTPException(status_code=500, detail="Project app update failed")
        return self._to_app_response(record)

    async def delete_app(self, *, project_id: int, app_id: int) -> None:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id, PERMISSION_MANAGE_PROJECT)
        app = await self.repository.get_app(app_id)
        if app is None or app.project_id != project_id:
            raise HTTPException(status_code=404, detail="Project app not found")
        await self.repository.delete_app(app)

    async def bulk_action_apps(
        self,
        *,
        project_id: int,
        payload: ProjectAppBulkActionRequest,
    ) -> ProjectAppBulkActionResponse:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_permission(project.team_id, PERMISSION_MANAGE_PROJECT)

        normalized_ids = [app_id for app_id in payload.app_ids if app_id > 0]
        if not normalized_ids:
            raise HTTPException(status_code=400, detail="Project app ids are required")
        app_ids = list(dict.fromkeys(normalized_ids))

        apps = await self.repository.get_apps(app_ids)
        if len(apps) != len(app_ids) or any(app.project_id != project_id for app in apps):
            raise HTTPException(status_code=404, detail="One or more project apps were not found")

        if payload.action == "enable":
            for app in apps:
                app.is_active = True
        elif payload.action == "disable":
            for app in apps:
                app.is_active = False
        else:
            for app in apps:
                await self.db.delete(app)

        await self.db.commit()
        return ProjectAppBulkActionResponse(
            action=payload.action,
            affected_ids=app_ids,
            affected_count=len(app_ids),
        )
