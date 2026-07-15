"""Agent integration endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.application.agent_integration_service import AgentIntegrationService
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.agent_integration import (
    AgentAppToolSetBindingCreate,
    AgentAppToolSetBindingListResponse,
    AgentAppToolSetBindingResponse,
    AgentToolCallLogListResponse,
    AgentToolCreate,
    AgentToolListResponse,
    AgentToolPublishResponse,
    AgentToolResponse,
    AgentToolTestRequest,
    AgentToolTestResponse,
    AgentToolUpdate,
    McpServerCreate,
    McpServerListResponse,
    McpServerResponse,
    McpServerTestResponse,
    McpServerUpdate,
    McpToolEnabledUpdate,
    McpToolListResponse,
    McpToolResponse,
    McpToolSyncResponse,
)

router = APIRouter()


def _service(db: AsyncSession, _current_user: User) -> AgentIntegrationService:
    return AgentIntegrationService(db)


@router.get("/mcp-servers", response_model=McpServerListResponse)
async def list_mcp_servers(
    team_id: int | None = Query(None),
    keyword: str | None = Query(None),
    status: str = Query("all", pattern="^(all|untested|available|error)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_mcp_servers(team_id=team_id, keyword=keyword, status=status, page=page, page_size=page_size)


@router.post("/mcp-servers", response_model=McpServerResponse)
async def create_mcp_server(
    body: McpServerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).create_mcp_server(body)


@router.put("/mcp-servers/{server_id}", response_model=McpServerResponse)
async def update_mcp_server(
    server_id: int,
    body: McpServerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).update_mcp_server(server_id, body)


@router.delete("/mcp-servers/{server_id}")
async def delete_mcp_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).delete_mcp_server(server_id)
    return {"message": "Deleted successfully"}


@router.post("/mcp-servers/{server_id}/test", response_model=McpServerTestResponse)
async def test_mcp_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).test_mcp_server(server_id)


@router.post("/mcp-servers/{server_id}/sync", response_model=McpToolSyncResponse)
async def sync_mcp_tools(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).sync_mcp_tools(server_id)


@router.get("/mcp-tools", response_model=McpToolListResponse)
async def list_mcp_tools(
    team_id: int | None = Query(None),
    server_id: int | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_mcp_tools(team_id=team_id, server_id=server_id, keyword=keyword, page=page, page_size=page_size)


@router.put("/mcp-tools/{tool_id}/enabled", response_model=McpToolResponse)
async def update_mcp_tool_enabled(
    tool_id: int,
    body: McpToolEnabledUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).update_mcp_tool_enabled(tool_id, body)


@router.get("/agent-tools", response_model=AgentToolListResponse)
async def list_agent_tools(
    team_id: int | None = Query(None),
    keyword: str | None = Query(None),
    enabled_status: str = Query("all", pattern="^(all|enabled|disabled)$"),
    lifecycle_status: str = Query("all", pattern="^(all|draft|verified|published|error)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_agent_tools(
        team_id=team_id,
        keyword=keyword,
        enabled_status=enabled_status,
        lifecycle_status=lifecycle_status,
        page=page,
        page_size=page_size,
    )


@router.post("/agent-tools", response_model=AgentToolResponse)
async def create_agent_tool(
    body: AgentToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).create_agent_tool(body)


@router.get("/agent-tools/{tool_id}", response_model=AgentToolResponse)
async def get_agent_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).get_agent_tool(tool_id)


@router.put("/agent-tools/{tool_id}", response_model=AgentToolResponse)
async def update_agent_tool(
    tool_id: int,
    body: AgentToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).update_agent_tool(tool_id, body)


@router.post("/agent-tools/{tool_id}/test", response_model=AgentToolTestResponse)
async def test_agent_tool(
    tool_id: int,
    body: AgentToolTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).test_agent_tool(tool_id, body)


@router.post("/agent-tools/{tool_id}/publish", response_model=AgentToolPublishResponse)
async def publish_agent_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).publish_agent_tool(tool_id)


@router.post("/agent-tools/{tool_id}/unpublish", response_model=AgentToolPublishResponse)
async def unpublish_agent_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).unpublish_agent_tool(tool_id)


@router.delete("/agent-tools/{tool_id}")
async def delete_agent_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).delete_agent_tool(tool_id)
    return {"message": "Deleted successfully"}


@router.get(
    "/project-apps/{project_id}/{app_id}/tool-sets",
    response_model=AgentAppToolSetBindingListResponse,
)
async def list_project_app_tool_set_bindings(
    project_id: int,
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).list_project_app_tool_set_bindings(
        project_id=project_id,
        app_id=app_id,
    )


@router.post(
    "/project-apps/{project_id}/{app_id}/tool-sets",
    response_model=AgentAppToolSetBindingResponse,
)
async def bind_project_app_tool_set(
    project_id: int,
    app_id: int,
    body: AgentAppToolSetBindingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    return await _service(db, current_user).bind_project_app_tool_set(
        project_id=project_id,
        app_id=app_id,
        payload=body,
    )


@router.delete("/project-apps/{project_id}/{app_id}/tool-sets/{binding_id}")
async def unbind_project_app_tool_set(
    project_id: int,
    app_id: int,
    binding_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _service(db, current_user).unbind_project_app_tool_set(
        project_id=project_id,
        app_id=app_id,
        binding_id=binding_id,
    )
    return {"message": "Deleted successfully"}


@router.get("/call-logs", response_model=AgentToolCallLogListResponse)
async def list_agent_tool_call_logs(
    team_id: int | None = Query(None),
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
    return await _service(db, current_user).list_call_logs(
        team_id=team_id,
        agent_tool_id=agent_tool_id,
        project_app_id=project_app_id,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        page=page,
        page_size=page_size,
    )
