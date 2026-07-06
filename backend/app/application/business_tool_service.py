"""Application service for business connections, APIs, tools and implementations."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.business_operations.http_tool_gateway import BusinessToolGateway
from app.application.business_operations.registry import BusinessOperationRegistry
from app.application.business_operations.schemas import (
    BusinessOperationActor,
    BusinessOperationRequest,
)
from app.application.permission_service import PermissionService
from app.core.authz import PERMISSION_MANAGE_PROJECT, PERMISSION_VIEW_TEAM_RESOURCE
from app.db.models import (
    BusinessApi,
    BusinessConnection,
    BusinessTool,
    BusinessToolImplementation,
    ProjectAppBusinessToolBinding,
    User,
)
from app.models.schemas.business_tool import (
    BusinessApiCreate,
    BusinessApiListResponse,
    BusinessApiResponse,
    BusinessApiUpdate,
    BusinessConnectionCreate,
    BusinessConnectionListResponse,
    BusinessConnectionResponse,
    BusinessConnectionTestResponse,
    BusinessConnectionUpdate,
    BusinessToolCallLogListResponse,
    BusinessToolCallLogResponse,
    BusinessToolCreate,
    BusinessToolImplementationCreate,
    BusinessToolImplementationListResponse,
    BusinessToolImplementationResponse,
    BusinessToolImplementationSummary,
    BusinessToolImplementationUpdate,
    BusinessToolListResponse,
    BusinessToolPublishResponse,
    BusinessToolResponse,
    BusinessToolTestRequest,
    BusinessToolTestResponse,
    BusinessToolUpdate,
    ProjectAppBusinessToolBindingCreate,
    ProjectAppBusinessToolBindingListResponse,
    ProjectAppBusinessToolBindingResponse,
)
from app.repositories.business_tool_repository import (
    BusinessApiRecord,
    BusinessConnectionRecord,
    BusinessToolCallLogRecord,
    BusinessToolImplementationRecord,
    BusinessToolRecord,
    BusinessToolRepository,
    ProjectAppBusinessToolBindingRecord,
)
from app.repositories.project_repository import ProjectRepository
from app.utils.time import utc_now


class BusinessToolService:
    """Coordinate connection, API, tool, implementation and binding use cases."""

    def __init__(self, db: AsyncSession, *, user_id: int, user: User | None = None):
        self.db = db
        self.user_id = user_id
        self.user = user
        self.repository = BusinessToolRepository(db)
        self.project_repository = ProjectRepository(db)
        self.permission_service = PermissionService(db)
        self.gateway = BusinessToolGateway()
        self.registry = BusinessOperationRegistry()

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None

    @staticmethod
    def _normalize_key(value: str, *, label: str) -> str:
        key = BusinessToolRepository.normalize_key(value)
        if not key:
            raise HTTPException(status_code=400, detail=f"{label}不能为空")
        return key

    @staticmethod
    def _normalize_method(method: str) -> str:
        normalized = str(method or "").strip().upper()
        if normalized not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise HTTPException(status_code=400, detail="不支持的请求方法")
        return normalized

    @staticmethod
    def _normalize_url(url: str) -> str:
        normalized = str(url or "").strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="连接地址必须是有效的 HTTP 或 HTTPS 地址")
        if parsed.username or parsed.password:
            raise HTTPException(status_code=400, detail="连接地址不能包含用户名或密码")
        return normalized

    @staticmethod
    def _normalize_relative_path(path: str, *, label: str) -> str:
        normalized = str(path or "").strip()
        parsed = urlparse(normalized)
        if parsed.scheme or parsed.netloc or normalized.startswith("//"):
            raise HTTPException(status_code=400, detail=f"{label}必须是连接内的相对路径")
        if not normalized:
            raise HTTPException(status_code=400, detail=f"{label}不能为空")
        return f"/{normalized.lstrip('/')}"

    @staticmethod
    def _normalize_typical_queries(values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = str(value or "").strip()
            if item and item not in result:
                result.append(item[:200])
        return result[:20]

    async def _ensure_team_permission(
        self,
        team_id: int,
        permission: str = PERMISSION_VIEW_TEAM_RESOURCE,
    ) -> None:
        if self.user is None:
            raise HTTPException(status_code=403, detail="无权访问该团队")
        if permission == PERMISSION_VIEW_TEAM_RESOURCE:
            allowed = await self.permission_service.can_access_team(self.user, team_id)
        else:
            allowed = await self.permission_service.has_team_permission(self.user, team_id, permission)
        if not allowed:
            raise HTTPException(status_code=403, detail="无权访问该团队")

    async def _resolve_accessible_team_ids(self, team_id: int | None) -> list[int] | None:
        if self.user is None:
            raise HTTPException(status_code=403, detail="无权访问团队资源")
        if team_id is not None:
            await self._ensure_team_permission(team_id)
            return None
        return await self.permission_service.list_accessible_team_ids(self.user)

    async def _get_project_app_for_manage(self, *, project_id: int, app_id: int):
        project = await self.project_repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        await self._ensure_team_permission(project.team_id, PERMISSION_MANAGE_PROJECT)
        app = await self.project_repository.get_app(app_id)
        if app is None or app.project_id != project_id:
            raise HTTPException(status_code=404, detail="应用端不存在")
        return project, app

    @staticmethod
    def _to_connection_response(record: BusinessConnectionRecord) -> BusinessConnectionResponse:
        connection = record.connection
        return BusinessConnectionResponse(
            id=connection.id,
            team_id=connection.team_id,
            team_name=record.team_name,
            name=connection.name,
            description=connection.description,
            environment=connection.environment,
            base_url=connection.base_url,
            auth_type=connection.auth_type,
            auth_secret_ref=connection.auth_secret_ref,
            auth_header_name=connection.auth_header_name,
            enabled=connection.enabled,
            status=connection.status,
            last_tested_at=connection.last_tested_at,
            last_test_error=connection.last_test_error,
            tool_count=record.tool_count,
            api_count=record.api_count,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )

    @staticmethod
    def _to_api_response(record: BusinessApiRecord) -> BusinessApiResponse:
        api = record.api
        connection = record.connection
        return BusinessApiResponse(
            id=api.id,
            team_id=api.team_id,
            team_name=record.team_name,
            connection_id=api.connection_id,
            connection_name=connection.name,
            connection_environment=connection.environment,
            connection_status=connection.status,
            api_key=api.api_key,
            name=api.name,
            description=api.description or "",
            method=api.method,
            path=api.path,
            request_schema=api.request_schema or {},
            response_schema=api.response_schema or {},
            source_type=api.source_type,
            source_version=api.source_version,
            enabled=api.enabled,
            created_at=api.created_at,
            updated_at=api.updated_at,
        )

    @staticmethod
    def _to_implementation_summary(
        record: BusinessToolImplementationRecord | None,
    ) -> BusinessToolImplementationSummary | None:
        if record is None:
            return None
        implementation = record.implementation
        api = record.api
        connection = record.connection
        return BusinessToolImplementationSummary(
            implementation_id=implementation.id,
            business_api_id=api.id,
            api_key=api.api_key,
            api_name=api.name,
            method=api.method,
            path=api.path,
            connection_id=connection.id,
            connection_name=connection.name,
            connection_environment=connection.environment,
            connection_status=connection.status,
            implementation_status=implementation.status,
            enabled=implementation.enabled,
            priority=implementation.priority,
        )

    def _to_implementation_response(
        self,
        record: BusinessToolImplementationRecord,
    ) -> BusinessToolImplementationResponse:
        implementation = record.implementation
        api = record.api
        connection = record.connection
        return BusinessToolImplementationResponse(
            id=implementation.id,
            business_tool_id=implementation.business_tool_id,
            business_api_id=api.id,
            api_key=api.api_key,
            api_name=api.name,
            method=api.method,
            path=api.path,
            connection_id=connection.id,
            connection_name=connection.name,
            connection_environment=connection.environment,
            connection_status=connection.status,
            implementation_type=implementation.implementation_type,
            context_binding=implementation.context_binding or {},
            request_mapping=implementation.request_mapping or {},
            response_mapping=implementation.response_mapping or {},
            priority=implementation.priority,
            enabled=implementation.enabled,
            status=implementation.status,
            last_tested_at=implementation.last_tested_at,
            last_test_error=implementation.last_test_error,
            created_at=implementation.created_at,
            updated_at=implementation.updated_at,
        )

    def _to_tool_response(self, record: BusinessToolRecord) -> BusinessToolResponse:
        tool = record.tool
        return BusinessToolResponse(
            id=tool.id,
            team_id=tool.team_id,
            team_name=record.team_name,
            tool_key=tool.tool_key,
            name=tool.name,
            description=tool.description or "",
            typical_queries=tool.typical_queries or [],
            params_schema=tool.params_schema or [],
            risk_level=tool.risk_level,
            requires_confirmation=tool.requires_confirmation,
            status=tool.status,
            last_tested_at=tool.last_tested_at,
            last_test_error=tool.last_test_error,
            enabled=tool.enabled,
            implementation_count=record.implementation_count,
            primary_implementation=self._to_implementation_summary(record.primary_implementation),
            created_at=tool.created_at,
            updated_at=tool.updated_at,
        )

    def _to_binding_response(
        self,
        record: ProjectAppBusinessToolBindingRecord,
    ) -> ProjectAppBusinessToolBindingResponse:
        binding = record.binding
        tool = record.tool
        implementation = record.primary_implementation
        reasons: list[str] = []
        if not binding.enabled:
            reasons.append("授权已停用")
        if not tool.enabled:
            reasons.append("工具已停用")
        if tool.status != "published":
            reasons.append("工具未发布")
        if implementation is None:
            reasons.append("工具没有可执行实现")
        else:
            if not implementation.implementation.enabled:
                reasons.append("实现已停用")
            if implementation.implementation.status != "published":
                reasons.append("实现未发布")
            if not implementation.api.enabled:
                reasons.append("接口已停用")
            if not implementation.connection.enabled:
                reasons.append("连接已停用")
            if implementation.connection.status != "available":
                reasons.append("连接不可用")
        return ProjectAppBusinessToolBindingResponse(
            id=binding.id,
            project_app_id=binding.project_app_id,
            business_tool_id=tool.id,
            tool_key=tool.tool_key,
            name=tool.name,
            description=tool.description,
            risk_level=tool.risk_level,
            status=tool.status,
            enabled=binding.enabled,
            tool_enabled=tool.enabled,
            is_available=not reasons,
            unavailable_reason="、".join(reasons) or None,
            primary_implementation=self._to_implementation_summary(implementation),
            created_at=binding.created_at,
            updated_at=binding.updated_at,
        )

    @staticmethod
    def _to_log_response(record: BusinessToolCallLogRecord) -> BusinessToolCallLogResponse:
        log = record.log
        return BusinessToolCallLogResponse(
            id=log.id,
            team_id=log.team_id,
            team_name=record.team_name,
            project_app_id=log.project_app_id,
            project_app_name=record.project_app_name,
            business_tool_id=log.business_tool_id,
            business_api_id=log.business_api_id,
            business_tool_implementation_id=log.business_tool_implementation_id,
            tool_key=log.tool_key,
            tool_name=log.tool_name,
            api_key=log.api_key,
            api_name=log.api_name,
            session_id=log.session_id,
            external_user_id=log.external_user_id,
            status=log.status,
            http_status=log.http_status,
            duration_ms=log.duration_ms,
            request_payload=log.request_payload or {},
            response_payload=log.response_payload or {},
            error_message=log.error_message,
            created_at=log.created_at,
        )

    async def list_connections(
        self,
        *,
        team_id: int | None = None,
        keyword: str | None = None,
        status: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> BusinessConnectionListResponse:
        accessible_team_ids = await self._resolve_accessible_team_ids(team_id)
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        total = await self.repository.count_connections(
            team_id=team_id,
            team_ids=accessible_team_ids,
            keyword=keyword,
            status=status,
        )
        records = await self.repository.list_connections_page(
            team_id=team_id,
            team_ids=accessible_team_ids,
            keyword=keyword,
            status=status,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return BusinessConnectionListResponse(
            items=[self._to_connection_response(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_connection(
        self,
        payload: BusinessConnectionCreate,
    ) -> BusinessConnectionResponse:
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        name = payload.name.strip()
        if await self.repository.connection_name_exists(team_id=payload.team_id, name=name):
            raise HTTPException(status_code=400, detail="同一团队下连接名称不能重复")
        self._validate_auth(payload.auth_type, payload.auth_secret_ref, payload.auth_header_name)
        connection = BusinessConnection(
            team_id=payload.team_id,
            name=name,
            description=self._normalize_optional_text(payload.description),
            environment=payload.environment,
            base_url=self._normalize_url(payload.base_url),
            auth_type=payload.auth_type,
            auth_secret_ref=self._normalize_optional_text(payload.auth_secret_ref),
            auth_header_name=self._normalize_optional_text(payload.auth_header_name),
            enabled=payload.enabled,
            status="untested",
        )
        await self.repository.save_connection(connection)
        record = await self.repository.get_connection_record(connection.id)
        if record is None:
            raise HTTPException(status_code=500, detail="连接创建失败")
        return self._to_connection_response(record)

    async def update_connection(
        self,
        connection_id: int,
        payload: BusinessConnectionUpdate,
    ) -> BusinessConnectionResponse:
        connection = await self.repository.get_connection(connection_id)
        if connection is None:
            raise HTTPException(status_code=404, detail="业务连接不存在")
        await self._ensure_team_permission(connection.team_id, PERMISSION_MANAGE_PROJECT)
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        if payload.team_id != connection.team_id and await self.repository.count_apis_for_connection(connection.id):
            raise HTTPException(status_code=400, detail="存在关联接口时不能变更连接所属团队")
        name = payload.name.strip()
        if await self.repository.connection_name_exists(
            team_id=payload.team_id,
            name=name,
            exclude_id=connection_id,
        ):
            raise HTTPException(status_code=400, detail="同一团队下连接名称不能重复")
        self._validate_auth(payload.auth_type, payload.auth_secret_ref, payload.auth_header_name)
        connection.team_id = payload.team_id
        connection.name = name
        connection.description = self._normalize_optional_text(payload.description)
        connection.environment = payload.environment
        connection.base_url = self._normalize_url(payload.base_url)
        connection.auth_type = payload.auth_type
        connection.auth_secret_ref = self._normalize_optional_text(payload.auth_secret_ref)
        connection.auth_header_name = self._normalize_optional_text(payload.auth_header_name)
        connection.enabled = payload.enabled
        connection.status = "untested"
        connection.last_test_error = None
        await self.repository.save_connection(connection)
        record = await self.repository.get_connection_record(connection.id)
        if record is None:
            raise HTTPException(status_code=500, detail="连接更新失败")
        return self._to_connection_response(record)

    async def test_connection(self, connection_id: int) -> BusinessConnectionTestResponse:
        connection = await self.repository.get_connection(connection_id)
        if connection is None:
            raise HTTPException(status_code=404, detail="业务连接不存在")
        await self._ensure_team_permission(connection.team_id, PERMISSION_MANAGE_PROJECT)
        success, http_status, duration_ms, message = await self.gateway.test_connection(connection)
        connection.status = "available" if success else "error"
        connection.last_tested_at = utc_now()
        connection.last_test_error = None if success else message
        await self.repository.save_connection(connection)
        return BusinessConnectionTestResponse(
            success=success,
            status=connection.status,
            http_status=http_status,
            duration_ms=duration_ms,
            message=message,
        )

    async def delete_connection(self, connection_id: int) -> None:
        connection = await self.repository.get_connection(connection_id)
        if connection is None:
            raise HTTPException(status_code=404, detail="业务连接不存在")
        await self._ensure_team_permission(connection.team_id, PERMISSION_MANAGE_PROJECT)
        if await self.repository.count_apis_for_connection(connection.id):
            raise HTTPException(status_code=400, detail="请先删除该连接下的接口")
        await self.repository.delete_connection(connection)

    async def list_apis(
        self,
        *,
        team_id: int | None = None,
        keyword: str | None = None,
        enabled_status: str = "all",
        connection_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BusinessApiListResponse:
        accessible_team_ids = await self._resolve_accessible_team_ids(team_id)
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        enabled = True if enabled_status == "enabled" else False if enabled_status == "disabled" else None
        total = await self.repository.count_apis(
            team_id=team_id,
            team_ids=accessible_team_ids,
            keyword=keyword,
            enabled=enabled,
            connection_id=connection_id,
        )
        records = await self.repository.list_apis_page(
            team_id=team_id,
            team_ids=accessible_team_ids,
            keyword=keyword,
            enabled=enabled,
            connection_id=connection_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return BusinessApiListResponse(
            items=[self._to_api_response(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_api(self, api_id: int) -> BusinessApiResponse:
        record = await self.repository.get_api_record(api_id)
        if record is None:
            raise HTTPException(status_code=404, detail="业务接口不存在")
        await self._ensure_team_permission(record.api.team_id)
        return self._to_api_response(record)

    async def create_api(self, payload: BusinessApiCreate) -> BusinessApiResponse:
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        connection = await self._validate_api_connection(payload.team_id, payload.connection_id)
        api_key = self._normalize_key(payload.api_key, label="接口标识")
        if await self.repository.api_key_exists(team_id=payload.team_id, api_key=api_key):
            raise HTTPException(status_code=400, detail="同一团队下接口标识不能重复")
        api = BusinessApi(
            team_id=payload.team_id,
            connection_id=connection.id,
            api_key=api_key,
            name=payload.name.strip(),
            description=payload.description.strip(),
            method=self._normalize_method(payload.method),
            path=self._normalize_relative_path(payload.path, label="接口路径"),
            request_schema=payload.request_schema.model_dump(by_alias=True),
            response_schema=payload.response_schema.model_dump(by_alias=True),
            source_type=payload.source_type,
            source_version=self._normalize_optional_text(payload.source_version),
            enabled=payload.enabled,
        )
        await self.repository.save_api(api)
        record = await self.repository.get_api_record(api.id)
        if record is None:
            raise HTTPException(status_code=500, detail="业务接口创建失败")
        return self._to_api_response(record)

    async def update_api(self, api_id: int, payload: BusinessApiUpdate) -> BusinessApiResponse:
        api = await self.repository.get_api(api_id)
        if api is None:
            raise HTTPException(status_code=404, detail="业务接口不存在")
        await self._ensure_team_permission(api.team_id, PERMISSION_MANAGE_PROJECT)
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        connection = await self._validate_api_connection(payload.team_id, payload.connection_id)
        api_key = self._normalize_key(payload.api_key, label="接口标识")
        if await self.repository.api_key_exists(
            team_id=payload.team_id,
            api_key=api_key,
            exclude_id=api_id,
        ):
            raise HTTPException(status_code=400, detail="同一团队下接口标识不能重复")
        api.team_id = payload.team_id
        api.connection_id = connection.id
        api.api_key = api_key
        api.name = payload.name.strip()
        api.description = payload.description.strip()
        api.method = self._normalize_method(payload.method)
        api.path = self._normalize_relative_path(payload.path, label="接口路径")
        api.request_schema = payload.request_schema.model_dump(by_alias=True)
        api.response_schema = payload.response_schema.model_dump(by_alias=True)
        api.source_type = payload.source_type
        api.source_version = self._normalize_optional_text(payload.source_version)
        api.enabled = payload.enabled
        await self.repository.save_api(api)
        record = await self.repository.get_api_record(api.id)
        if record is None:
            raise HTTPException(status_code=500, detail="业务接口更新失败")
        return self._to_api_response(record)

    async def delete_api(self, api_id: int) -> None:
        api = await self.repository.get_api(api_id)
        if api is None:
            raise HTTPException(status_code=404, detail="业务接口不存在")
        await self._ensure_team_permission(api.team_id, PERMISSION_MANAGE_PROJECT)
        if await self.repository.count_implementations_for_api(api.id):
            raise HTTPException(status_code=400, detail="请先删除或迁移依赖该接口的实现")
        await self.repository.delete_api(api)

    async def list_tools(
        self,
        *,
        team_id: int | None = None,
        keyword: str | None = None,
        enabled_status: str = "all",
        lifecycle_status: str = "all",
        connection_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> BusinessToolListResponse:
        accessible_team_ids = await self._resolve_accessible_team_ids(team_id)
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        enabled = True if enabled_status == "enabled" else False if enabled_status == "disabled" else None
        total = await self.repository.count_tools(
            team_id=team_id,
            team_ids=accessible_team_ids,
            keyword=keyword,
            enabled=enabled,
            status=lifecycle_status,
            connection_id=connection_id,
        )
        records = await self.repository.list_tools_page(
            team_id=team_id,
            team_ids=accessible_team_ids,
            keyword=keyword,
            enabled=enabled,
            status=lifecycle_status,
            connection_id=connection_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return BusinessToolListResponse(
            items=[self._to_tool_response(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_tool(self, tool_id: int) -> BusinessToolResponse:
        record = await self.repository.get_tool_record(tool_id)
        if record is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(record.tool.team_id)
        return self._to_tool_response(record)

    async def create_tool(self, payload: BusinessToolCreate) -> BusinessToolResponse:
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        tool_key = self._normalize_key(payload.tool_key, label="工具标识")
        if await self.repository.tool_key_exists(team_id=payload.team_id, tool_key=tool_key):
            raise HTTPException(status_code=400, detail="同一团队下工具标识不能重复")
        tool = BusinessTool(
            team_id=payload.team_id,
            tool_key=tool_key,
            name=payload.name.strip(),
            description=payload.description.strip(),
            typical_queries=self._normalize_typical_queries(payload.typical_queries),
            params_schema=[item.model_dump() for item in payload.params_schema],
            risk_level=payload.risk_level,
            requires_confirmation=payload.requires_confirmation or payload.risk_level == "high",
            status="draft",
            enabled=payload.enabled,
        )
        await self.repository.save_tool(tool)
        record = await self.repository.get_tool_record(tool.id)
        if record is None:
            raise HTTPException(status_code=500, detail="业务工具创建失败")
        return self._to_tool_response(record)

    async def update_tool(self, tool_id: int, payload: BusinessToolUpdate) -> BusinessToolResponse:
        tool = await self.repository.get_tool(tool_id)
        if tool is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(tool.team_id, PERMISSION_MANAGE_PROJECT)
        await self._ensure_team_permission(payload.team_id, PERMISSION_MANAGE_PROJECT)
        if payload.team_id != tool.team_id:
            raise HTTPException(status_code=400, detail="业务工具创建后不能变更所属团队")
        tool_key = self._normalize_key(payload.tool_key, label="工具标识")
        if await self.repository.tool_key_exists(
            team_id=payload.team_id,
            tool_key=tool_key,
            exclude_id=tool_id,
        ):
            raise HTTPException(status_code=400, detail="同一团队下工具标识不能重复")
        tool.team_id = payload.team_id
        tool.tool_key = tool_key
        tool.name = payload.name.strip()
        tool.description = payload.description.strip()
        tool.typical_queries = self._normalize_typical_queries(payload.typical_queries)
        tool.params_schema = [item.model_dump() for item in payload.params_schema]
        tool.risk_level = payload.risk_level
        tool.requires_confirmation = payload.requires_confirmation or payload.risk_level == "high"
        tool.enabled = payload.enabled
        if tool.status == "published":
            tool.status = "verified"
        tool.last_test_error = None
        await self.repository.save_tool(tool)
        record = await self.repository.get_tool_record(tool.id)
        if record is None:
            raise HTTPException(status_code=500, detail="业务工具更新失败")
        return self._to_tool_response(record)

    async def delete_tool(self, tool_id: int) -> None:
        tool = await self.repository.get_tool(tool_id)
        if tool is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(tool.team_id, PERMISSION_MANAGE_PROJECT)
        if await self.repository.count_implementations_for_tool(tool.id):
            raise HTTPException(status_code=400, detail="请先删除该工具下的实现")
        await self.repository.delete_tool(tool)

    async def list_tool_implementations(self, tool_id: int) -> BusinessToolImplementationListResponse:
        record = await self.repository.get_tool_record(tool_id)
        if record is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(record.tool.team_id)
        implementations = await self.repository.list_tool_implementations(tool_id=tool_id)
        return BusinessToolImplementationListResponse(
            items=[self._to_implementation_response(item) for item in implementations]
        )

    async def create_tool_implementation(
        self,
        tool_id: int,
        payload: BusinessToolImplementationCreate,
    ) -> BusinessToolImplementationResponse:
        tool = await self.repository.get_tool(tool_id)
        if tool is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(tool.team_id, PERMISSION_MANAGE_PROJECT)
        api_record = await self.repository.get_api_record(payload.business_api_id)
        if api_record is None:
            raise HTTPException(status_code=404, detail="业务接口不存在")
        if api_record.api.team_id != tool.team_id:
            raise HTTPException(status_code=400, detail="业务工具与接口不属于同一团队")
        implementation = BusinessToolImplementation(
            business_tool_id=tool.id,
            business_api_id=api_record.api.id,
            implementation_type=payload.implementation_type,
            context_binding=payload.context_binding,
            request_mapping=payload.request_mapping,
            response_mapping=payload.response_mapping,
            status="draft",
            priority=payload.priority,
            enabled=payload.enabled,
        )
        await self.repository.save_tool_implementation(implementation)
        record = await self.repository.get_tool_implementation_record(implementation.id)
        if record is None:
            raise HTTPException(status_code=500, detail="工具实现创建失败")
        return self._to_implementation_response(record)

    async def update_tool_implementation(
        self,
        implementation_id: int,
        payload: BusinessToolImplementationUpdate,
    ) -> BusinessToolImplementationResponse:
        implementation = await self.repository.get_tool_implementation(implementation_id)
        if implementation is None:
            raise HTTPException(status_code=404, detail="工具实现不存在")
        tool = await self.repository.get_tool(implementation.business_tool_id)
        if tool is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(tool.team_id, PERMISSION_MANAGE_PROJECT)
        api_record = await self.repository.get_api_record(payload.business_api_id)
        if api_record is None:
            raise HTTPException(status_code=404, detail="业务接口不存在")
        if api_record.api.team_id != tool.team_id:
            raise HTTPException(status_code=400, detail="业务工具与接口不属于同一团队")
        implementation.business_api_id = api_record.api.id
        implementation.implementation_type = payload.implementation_type
        implementation.context_binding = payload.context_binding
        implementation.request_mapping = payload.request_mapping
        implementation.response_mapping = payload.response_mapping
        implementation.priority = payload.priority
        implementation.enabled = payload.enabled
        if implementation.status == "published":
            implementation.status = "verified"
        implementation.last_test_error = None
        await self.repository.save_tool_implementation(implementation)
        record = await self.repository.get_tool_implementation_record(implementation.id)
        if record is None:
            raise HTTPException(status_code=500, detail="工具实现更新失败")
        return self._to_implementation_response(record)

    async def delete_tool_implementation(self, implementation_id: int) -> None:
        implementation = await self.repository.get_tool_implementation(implementation_id)
        if implementation is None:
            raise HTTPException(status_code=404, detail="工具实现不存在")
        tool = await self.repository.get_tool(implementation.business_tool_id)
        if tool is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(tool.team_id, PERMISSION_MANAGE_PROJECT)
        await self.repository.delete_tool_implementation(implementation)

    async def test_tool(
        self,
        tool_id: int,
        payload: BusinessToolTestRequest,
    ) -> BusinessToolTestResponse:
        record = await self.repository.get_tool_record(tool_id)
        if record is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(record.tool.team_id, PERMISSION_MANAGE_PROJECT)
        implementation_record = await self._resolve_tool_implementation_for_test(
            tool_id=tool_id,
            implementation_id=payload.implementation_id,
        )
        operation = self.registry.from_tool_record(record)
        missing = [
            param.label
            for param in operation.params
            if param.required and self._is_blank(payload.params.get(param.key))
        ]
        if missing:
            raise HTTPException(status_code=400, detail=f"请填写必填测试参数：{'、'.join(missing)}")
        result = await self.gateway.execute(
            operation=operation,
            tool=record.tool,
            implementation=implementation_record.implementation,
            api=implementation_record.api,
            connection=implementation_record.connection,
            request=BusinessOperationRequest(
                operation_id=record.tool.tool_key,
                actor=BusinessOperationActor(user_id=self.user_id),
                scope=payload.scope,
                params=payload.params,
            ),
        )
        implementation_record.implementation.last_tested_at = utc_now()
        implementation_record.implementation.status = "verified" if result.success else "error"
        implementation_record.implementation.last_test_error = None if result.success else result.message
        record.tool.last_tested_at = utc_now()
        record.tool.status = "verified" if result.success else "error"
        record.tool.last_test_error = None if result.success else result.message
        if result.success:
            implementation_record.connection.status = "available"
            implementation_record.connection.last_tested_at = utc_now()
            implementation_record.connection.last_test_error = None
            await self.repository.save_connection(implementation_record.connection)
        await self.repository.save_tool_implementation(implementation_record.implementation)
        await self.repository.save_tool(record.tool)
        return BusinessToolTestResponse(
            success=result.success,
            status=record.tool.status,
            implementation_id=implementation_record.implementation.id,
            http_status=result.http_status,
            duration_ms=result.duration_ms,
            message=result.message,
            data=result.data,
            error_code=result.error.code if result.error else None,
        )

    async def publish_tool(self, tool_id: int) -> BusinessToolPublishResponse:
        record = await self.repository.get_tool_record(tool_id)
        if record is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(record.tool.team_id, PERMISSION_MANAGE_PROJECT)
        implementation_records = await self.repository.list_tool_implementations(tool_id=tool_id)
        eligible = [
            item
            for item in implementation_records
            if item.implementation.enabled
            and item.implementation.status == "verified"
            and item.api.enabled
            and item.connection.enabled
            and item.connection.status == "available"
        ]
        if not eligible:
            raise HTTPException(status_code=400, detail="请先准备至少一个已验证且可用的工具实现")
        eligible_ids = {item.implementation.id for item in eligible}
        published_ids: list[int] = []
        for implementation_record in implementation_records:
            implementation = implementation_record.implementation
            if implementation.id in eligible_ids:
                implementation.status = "published"
                published_ids.append(implementation.id)
            elif implementation.status == "published":
                implementation.status = "verified"
            await self.repository.save_tool_implementation(implementation)
        record.tool.status = "published"
        await self.repository.save_tool(record.tool)
        return BusinessToolPublishResponse(
            id=record.tool.id,
            status="published",
            published_implementation_ids=published_ids,
            message="工具已发布",
        )

    async def unpublish_tool(self, tool_id: int) -> BusinessToolPublishResponse:
        tool = await self.repository.get_tool(tool_id)
        if tool is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        await self._ensure_team_permission(tool.team_id, PERMISSION_MANAGE_PROJECT)
        implementation_records = await self.repository.list_tool_implementations(tool_id=tool_id)
        for implementation_record in implementation_records:
            implementation = implementation_record.implementation
            if implementation.status == "published":
                implementation.status = (
                    "verified"
                    if implementation.last_tested_at and not implementation.last_test_error
                    else "draft"
                )
                await self.repository.save_tool_implementation(implementation)
        tool.status = "verified" if tool.last_tested_at and not tool.last_test_error else "draft"
        await self.repository.save_tool(tool)
        return BusinessToolPublishResponse(
            id=tool.id,
            status=tool.status,
            published_implementation_ids=[],
            message="工具已取消发布",
        )

    async def list_call_logs(
        self,
        *,
        team_id: int | None = None,
        tool_id: int | None = None,
        project_app_id: int | None = None,
        status: str = "all",
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BusinessToolCallLogListResponse:
        accessible_team_ids = await self._resolve_accessible_team_ids(team_id)
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        total = await self.repository.count_call_logs(
            team_id=team_id,
            team_ids=accessible_team_ids,
            tool_id=tool_id,
            project_app_id=project_app_id,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
        )
        records = await self.repository.list_call_logs_page(
            team_id=team_id,
            team_ids=accessible_team_ids,
            tool_id=tool_id,
            project_app_id=project_app_id,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return BusinessToolCallLogListResponse(
            items=[self._to_log_response(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_project_app_bindings(
        self,
        *,
        project_id: int,
        app_id: int,
    ) -> ProjectAppBusinessToolBindingListResponse:
        await self._get_project_app_for_manage(project_id=project_id, app_id=app_id)
        records = await self.repository.list_project_app_bindings(project_app_id=app_id)
        return ProjectAppBusinessToolBindingListResponse(
            items=[self._to_binding_response(record) for record in records]
        )

    async def bind_project_app_tool(
        self,
        *,
        project_id: int,
        app_id: int,
        payload: ProjectAppBusinessToolBindingCreate,
    ) -> ProjectAppBusinessToolBindingResponse:
        project, _app = await self._get_project_app_for_manage(project_id=project_id, app_id=app_id)
        record = await self.repository.get_tool_record(payload.business_tool_id)
        if record is None:
            raise HTTPException(status_code=404, detail="业务工具不存在")
        if record.tool.team_id != project.team_id:
            raise HTTPException(status_code=400, detail="业务工具与应用端不属于同一团队")
        binding = await self.repository.get_project_app_binding_by_tool(
            project_app_id=app_id,
            business_tool_id=record.tool.id,
        )
        if binding is None:
            binding = ProjectAppBusinessToolBinding(
                project_app_id=app_id,
                business_tool_id=record.tool.id,
                enabled=payload.enabled,
            )
        else:
            binding.enabled = payload.enabled
        binding = await self.repository.save_project_app_binding(binding)
        return self._to_binding_response(
            ProjectAppBusinessToolBindingRecord(
                binding=binding,
                tool=record.tool,
                primary_implementation=record.primary_implementation,
            )
        )

    async def unbind_project_app_tool(
        self,
        *,
        project_id: int,
        app_id: int,
        binding_id: int,
    ) -> None:
        await self._get_project_app_for_manage(project_id=project_id, app_id=app_id)
        binding = await self.repository.get_project_app_binding(binding_id)
        if binding is None or binding.project_app_id != app_id:
            raise HTTPException(status_code=404, detail="工具授权不存在")
        await self.repository.unbind_project_app_tool(binding)

    async def _resolve_tool_implementation_for_test(
        self,
        *,
        tool_id: int,
        implementation_id: int | None,
    ) -> BusinessToolImplementationRecord:
        if implementation_id is not None:
            record = await self.repository.get_tool_implementation_record(implementation_id)
            if record is None or record.implementation.business_tool_id != tool_id:
                raise HTTPException(status_code=404, detail="工具实现不存在")
            return record
        implementations = await self.repository.list_tool_implementations(tool_id=tool_id)
        for record in implementations:
            if record.implementation.enabled:
                return record
        raise HTTPException(status_code=400, detail="该工具当前没有可测试的实现")

    async def _validate_api_connection(self, team_id: int, connection_id: int) -> BusinessConnection:
        connection = await self.repository.get_connection(connection_id)
        if connection is None:
            raise HTTPException(status_code=404, detail="业务连接不存在")
        if connection.team_id != team_id:
            raise HTTPException(status_code=400, detail="业务连接与接口不属于同一团队")
        return connection

    @staticmethod
    def _validate_auth(auth_type: str, secret_ref: str | None, header_name: str | None) -> None:
        if auth_type in {"bearer", "header"} and not str(secret_ref or "").strip():
            raise HTTPException(status_code=400, detail="请填写密钥环境变量名称")
        if auth_type == "header" and not str(header_name or "").strip():
            raise HTTPException(status_code=400, detail="请填写自定义请求头名称")

    @staticmethod
    def _is_blank(value) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())
