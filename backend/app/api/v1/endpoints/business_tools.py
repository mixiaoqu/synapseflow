"""Business connection, tool, authorization and call-log endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.application.business_tool_service import BusinessToolService
from app.db.models import User
from app.db.session import get_db
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
    BusinessToolCreate,
    BusinessToolImplementationCreate,
    BusinessToolImplementationListResponse,
    BusinessToolImplementationResponse,
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

router = APIRouter()


def _service(db: AsyncSession, current_user: User) -> BusinessToolService:
    return BusinessToolService(db, user_id=current_user.id, user=current_user)


@router.get("/connections", response_model=BusinessConnectionListResponse)
async def list_business_connections(
    team_id: int | None = Query(None),
    keyword: str | None = Query(None),
    status: str = Query("all", pattern="^(all|untested|available|error)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_connections(
        team_id=team_id,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("/connections", response_model=BusinessConnectionResponse)
async def create_business_connection(
    body: BusinessConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).create_connection(body)


@router.put("/connections/{connection_id}", response_model=BusinessConnectionResponse)
async def update_business_connection(
    connection_id: int,
    body: BusinessConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).update_connection(connection_id, body)


@router.post("/connections/{connection_id}/test", response_model=BusinessConnectionTestResponse)
async def test_business_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).test_connection(connection_id)


@router.delete("/connections/{connection_id}")
async def delete_business_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).delete_connection(connection_id)
    return {"message": "Deleted successfully"}


@router.get("/apis", response_model=BusinessApiListResponse)
async def list_business_apis(
    team_id: int | None = Query(None),
    keyword: str | None = Query(None),
    enabled_status: str = Query("all", pattern="^(all|enabled|disabled)$"),
    connection_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_apis(
        team_id=team_id,
        keyword=keyword,
        enabled_status=enabled_status,
        connection_id=connection_id,
        page=page,
        page_size=page_size,
    )


@router.post("/apis", response_model=BusinessApiResponse)
async def create_business_api(
    body: BusinessApiCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).create_api(body)


@router.get("/apis/{api_id}", response_model=BusinessApiResponse)
async def get_business_api(
    api_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).get_api(api_id)


@router.put("/apis/{api_id}", response_model=BusinessApiResponse)
async def update_business_api(
    api_id: int,
    body: BusinessApiUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).update_api(api_id, body)


@router.delete("/apis/{api_id}")
async def delete_business_api(
    api_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).delete_api(api_id)
    return {"message": "Deleted successfully"}


@router.get("/logs", response_model=BusinessToolCallLogListResponse)
async def list_business_tool_call_logs(
    team_id: int | None = Query(None),
    tool_id: int | None = Query(None),
    project_app_id: int | None = Query(None),
    status: str = Query("all", pattern="^(all|success|error)$"),
    started_at: datetime | None = Query(None),
    ended_at: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_call_logs(
        team_id=team_id,
        tool_id=tool_id,
        project_app_id=project_app_id,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        page=page,
        page_size=page_size,
    )


@router.get("", response_model=BusinessToolListResponse)
async def list_business_tools(
    team_id: int | None = Query(None),
    keyword: str | None = Query(None),
    enabled_status: str = Query("all", pattern="^(all|enabled|disabled)$"),
    lifecycle_status: str = Query("all", pattern="^(all|draft|verified|published|error)$"),
    connection_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_tools(
        team_id=team_id,
        keyword=keyword,
        enabled_status=enabled_status,
        lifecycle_status=lifecycle_status,
        connection_id=connection_id,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=BusinessToolResponse)
async def create_business_tool(
    body: BusinessToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).create_tool(body)


@router.get("/{tool_id}", response_model=BusinessToolResponse)
async def get_business_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).get_tool(tool_id)


@router.put("/{tool_id}", response_model=BusinessToolResponse)
async def update_business_tool(
    tool_id: int,
    body: BusinessToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).update_tool(tool_id, body)


@router.get("/{tool_id}/implementations", response_model=BusinessToolImplementationListResponse)
async def list_business_tool_implementations(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_tool_implementations(tool_id)


@router.post("/{tool_id}/implementations", response_model=BusinessToolImplementationResponse)
async def create_business_tool_implementation(
    tool_id: int,
    body: BusinessToolImplementationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).create_tool_implementation(tool_id, body)


@router.post("/{tool_id}/test", response_model=BusinessToolTestResponse)
async def test_business_tool(
    tool_id: int,
    body: BusinessToolTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).test_tool(tool_id, body)


@router.post("/{tool_id}/publish", response_model=BusinessToolPublishResponse)
async def publish_business_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).publish_tool(tool_id)


@router.post("/{tool_id}/unpublish", response_model=BusinessToolPublishResponse)
async def unpublish_business_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).unpublish_tool(tool_id)


@router.delete("/{tool_id}")
async def delete_business_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).delete_tool(tool_id)
    return {"message": "Deleted successfully"}


@router.put("/implementations/{implementation_id}", response_model=BusinessToolImplementationResponse)
async def update_business_tool_implementation(
    implementation_id: int,
    body: BusinessToolImplementationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).update_tool_implementation(implementation_id, body)


@router.delete("/implementations/{implementation_id}")
async def delete_business_tool_implementation(
    implementation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).delete_tool_implementation(implementation_id)
    return {"message": "Deleted successfully"}


@router.get(
    "/project-apps/{project_id}/{app_id}/bindings",
    response_model=ProjectAppBusinessToolBindingListResponse,
)
async def list_project_app_business_tool_bindings(
    project_id: int,
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_project_app_bindings(
        project_id=project_id,
        app_id=app_id,
    )


@router.post(
    "/project-apps/{project_id}/{app_id}/bindings",
    response_model=ProjectAppBusinessToolBindingResponse,
)
async def bind_project_app_business_tool(
    project_id: int,
    app_id: int,
    body: ProjectAppBusinessToolBindingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).bind_project_app_tool(
        project_id=project_id,
        app_id=app_id,
        payload=body,
    )


@router.delete("/project-apps/{project_id}/{app_id}/bindings/{binding_id}")
async def unbind_project_app_business_tool(
    project_id: int,
    app_id: int,
    binding_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).unbind_project_app_tool(
        project_id=project_id,
        app_id=app_id,
        binding_id=binding_id,
    )
    return {"message": "Deleted successfully"}
