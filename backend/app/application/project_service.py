"""Project and project application application service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AssistantProfile, Product, Project, ProjectApp
from app.models.schemas.project import (
    ProjectAppKnowledgeBaseBindingResponse,
    ProjectAppCreate,
    ProjectAppResponse,
    ProjectAppUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.repositories.project_repository import (
    ProjectAppBindingRecord,
    ProjectAppRecord,
    ProjectAppRuntimeRecord,
    ProjectRecord,
    ProjectRepository,
)
from app.repositories.product_repository import ProductRepository
from app.repositories.team_repository import TeamRepository


class ProjectService:
    def __init__(self, db: AsyncSession, *, user_id: int):
        self.db = db
        self.user_id = user_id
        self.repository = ProjectRepository(db)
        self.product_repository = ProductRepository(db)
        self.team_repository = TeamRepository(db, user_id=user_id)

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
    def _to_binding_response(
        binding: ProjectAppBindingRecord,
    ) -> ProjectAppKnowledgeBaseBindingResponse:
        return ProjectAppKnowledgeBaseBindingResponse(
            knowledge_base_id=binding.knowledge_base_id,
            knowledge_base_name=binding.knowledge_base_name,
        )

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
            default_assistant_id=app.default_assistant_id,
            default_assistant_name=record.assistant_name,
            bindings=[ProjectService._to_binding_response(binding) for binding in record.bindings],
            is_active=app.is_active,
            created_at=app.created_at,
            updated_at=app.updated_at,
        )

    async def _ensure_team_access(self, team_id: int) -> None:
        if not await self.team_repository.can_access_team(team_id):
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

    async def _validate_bindings(
        self,
        *,
        project: Project,
        bindings: list,
    ) -> list[int]:
        if not bindings:
            raise HTTPException(
                status_code=400,
                detail="At least one knowledge base binding is required",
            )
        normalized: list[int] = []
        seen_knowledge_base_ids: set[int] = set()
        from app.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repository = KnowledgeBaseRepository(self.db, user_id=self.user_id)
        for item in bindings:
            knowledge_base_id = int(item.knowledge_base_id)
            if knowledge_base_id in seen_knowledge_base_ids:
                raise HTTPException(
                    status_code=400,
                    detail="Duplicate knowledge base binding is not allowed",
                )
            knowledge_base = await kb_repository.get_by_id(knowledge_base_id)
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
            seen_knowledge_base_ids.add(knowledge_base_id)
            normalized.append(knowledge_base_id)
        return normalized

    async def list_projects(self, *, team_id: int | None = None) -> list[ProjectResponse]:
        if team_id is not None:
            await self._ensure_team_access(team_id)
        records = await self.repository.list_projects(team_id=team_id)
        return [self._to_project_response(record) for record in records]

    async def get_project(self, project_id: int) -> ProjectResponse:
        record = await self.repository.get_project_record(project_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_access(record.project.team_id)
        return self._to_project_response(record)

    async def create_project(self, payload: ProjectCreate) -> ProjectResponse:
        await self._ensure_team_access(payload.team_id)
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
        await self._ensure_team_access(project.team_id)
        await self._ensure_team_access(payload.team_id)
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
        await self._ensure_team_access(project.team_id)
        await self.repository.delete_project(project)

    async def list_apps(self, *, project_id: int) -> list[ProjectAppResponse]:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_access(project.team_id)
        records = await self.repository.list_apps(project_id=project_id)
        return [self._to_app_response(record) for record in records]

    async def get_app(self, *, project_id: int, app_id: int) -> ProjectAppResponse:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_access(project.team_id)
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
        await self._ensure_team_access(project.team_id)
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
        await self._ensure_team_access(project.team_id)
        code = self._normalize_code(payload.code)
        if await self.repository.app_code_exists(project_id=project_id, code=code):
            raise HTTPException(status_code=400, detail="Project app code already exists")
        await self._get_assistant_for_project(
            project=project,
            assistant_id=payload.default_assistant_id,
        )
        normalized_bindings = await self._validate_bindings(
            project=project,
            bindings=payload.bindings,
        )
        app = ProjectApp(
            project_id=project_id,
            code=code,
            name=payload.name.strip(),
            description=self._normalize_optional_text(payload.description),
            default_assistant_id=payload.default_assistant_id,
            is_active=payload.is_active,
        )
        await self.repository.create_app(app, bindings=normalized_bindings)
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
        await self._ensure_team_access(project.team_id)
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
        normalized_bindings = await self._validate_bindings(
            project=project,
            bindings=payload.bindings,
        )
        app.code = code
        app.name = payload.name.strip()
        app.description = self._normalize_optional_text(payload.description)
        app.default_assistant_id = payload.default_assistant_id
        app.is_active = payload.is_active
        await self.repository.update_app(app, bindings=normalized_bindings)
        record = await self.repository.get_app_record(app.id)
        if record is None:
            raise HTTPException(status_code=500, detail="Project app update failed")
        return self._to_app_response(record)

    async def delete_app(self, *, project_id: int, app_id: int) -> None:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await self._ensure_team_access(project.team_id)
        app = await self.repository.get_app(app_id)
        if app is None or app.project_id != project_id:
            raise HTTPException(status_code=404, detail="Project app not found")
        await self.repository.delete_app(app)
