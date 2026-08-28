"""Tool provider catalog, governance, grant and audit endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.application.agent_tool_catalog_service import AgentToolCatalogService
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.tool_provider import (
    AgentToolBatchPublishRequest,
    AgentToolBatchPublishResponse,
    AgentToolGrantCreate,
    AgentToolGrantListResponse,
    AgentToolGrantReplace,
    AgentToolGrantResponse,
    AgentToolInvocationListResponse,
    AgentToolListResponse,
    AgentToolPublishResponse,
    AgentToolResponse,
    AgentToolSyncResponse,
    AgentToolTestRequest,
    AgentToolTestResponse,
    AgentToolUpdate,
    ToolProviderCreate,
    ToolProviderListResponse,
    ToolProviderResponse,
    ToolProviderTestResponse,
    ToolProviderUpdate,
)

router = APIRouter()


def _service(db: AsyncSession, user: User) -> AgentToolCatalogService:
    return AgentToolCatalogService(db, user=user)


@router.get("/tool-providers", response_model=ToolProviderListResponse)
async def list_tool_providers(
    team_id: int = Query(..., gt=0),
    keyword: str | None = Query(None),
    health_status: str = Query("all", pattern="^(all|untested|available|error)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_providers(
        team_id=team_id,
        keyword=keyword,
        health_status=health_status,
        page=page,
        page_size=page_size,
    )


@router.post("/tool-providers", response_model=ToolProviderResponse)
async def create_tool_provider(
    body: ToolProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).create_provider(body)


@router.put("/tool-providers/{provider_id}", response_model=ToolProviderResponse)
async def update_tool_provider(
    provider_id: int,
    body: ToolProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).update_provider(provider_id, body)


@router.delete("/tool-providers/{provider_id}")
async def delete_tool_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).delete_provider(provider_id)
    return {"message": "Deleted successfully"}


@router.post("/tool-providers/{provider_id}/test", response_model=ToolProviderTestResponse)
async def test_tool_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).test_provider(provider_id)


@router.post("/tool-providers/{provider_id}/sync", response_model=AgentToolSyncResponse)
async def sync_agent_tools(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).sync_tools(provider_id)


@router.get("/agent-tools", response_model=AgentToolListResponse)
async def list_agent_tools(
    team_id: int = Query(..., gt=0),
    provider_id: int | None = Query(None),
    keyword: str | None = Query(None),
    publish_status: str = Query("all", pattern="^(all|draft|published|needs_review)$"),
    sync_status: str = Query("all", pattern="^(all|active|removed|invalid)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_tools(
        team_id=team_id,
        provider_id=provider_id,
        keyword=keyword,
        publish_status=publish_status,
        sync_status=sync_status,
        page=page,
        page_size=page_size,
    )


@router.get("/agent-tools/{tool_id}", response_model=AgentToolResponse)
async def get_agent_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).get_tool(tool_id)


@router.post("/agent-tools/batch-publish", response_model=AgentToolBatchPublishResponse)
async def batch_publish_agent_tools(
    body: AgentToolBatchPublishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).batch_publish_tools(body)


@router.put("/agent-tools/{tool_id}", response_model=AgentToolResponse)
async def update_agent_tool(
    tool_id: int,
    body: AgentToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).update_tool(tool_id, body)


@router.post("/agent-tools/{tool_id}/test", response_model=AgentToolTestResponse)
async def test_agent_tool(
    tool_id: int,
    body: AgentToolTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).test_tool(tool_id, body)


@router.post("/agent-tools/{tool_id}/publish", response_model=AgentToolPublishResponse)
async def publish_agent_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).publish_tool(tool_id)


@router.post("/agent-tools/{tool_id}/unpublish", response_model=AgentToolPublishResponse)
async def unpublish_agent_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).unpublish_tool(tool_id)


@router.get(
    "/project-apps/{project_id}/{app_id}/tool-grants",
    response_model=AgentToolGrantListResponse,
)
async def list_agent_tool_grants(
    project_id: int,
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_grants(project_id=project_id, app_id=app_id)


@router.put(
    "/project-apps/{project_id}/{app_id}/tool-grants",
    response_model=AgentToolGrantListResponse,
)
async def replace_agent_tool_grants(
    project_id: int,
    app_id: int,
    body: AgentToolGrantReplace,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).replace_grants(
        project_id=project_id,
        app_id=app_id,
        payload=body,
    )


@router.post(
    "/project-apps/{project_id}/{app_id}/tool-grants",
    response_model=AgentToolGrantResponse,
)
async def create_agent_tool_grant(
    project_id: int,
    app_id: int,
    body: AgentToolGrantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).create_grant(
        project_id=project_id,
        app_id=app_id,
        payload=body,
    )


@router.delete("/project-apps/{project_id}/{app_id}/tool-grants/{grant_id}")
async def delete_agent_tool_grant(
    project_id: int,
    app_id: int,
    grant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).delete_grant(
        project_id=project_id,
        app_id=app_id,
        grant_id=grant_id,
    )
    return {"message": "Deleted successfully"}


@router.get("/tool-invocations", response_model=AgentToolInvocationListResponse)
async def list_agent_tool_invocations(
    team_id: int = Query(..., gt=0),
    agent_tool_id: int | None = Query(None),
    project_app_id: int | None = Query(None),
    status: str = Query("all", pattern="^(all|success|error)$"),
    started_at: datetime | None = Query(None),
    ended_at: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_invocations(
        team_id=team_id,
        agent_tool_id=agent_tool_id,
        project_app_id=project_app_id,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        page=page,
        page_size=page_size,
    )
