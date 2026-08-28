"""Read-only MCP endpoints for internal developer knowledge access."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.embed import require_enterprise_service_token
from app.api.dependencies.mcp_auth import McpAuthContext, get_mcp_auth_context
from app.application.mcp_service import McpService
from app.db.session import get_db
from app.models.schemas.mcp import (
    McpAnswerRequest,
    McpAnswerResponse,
    McpBootstrapRequest,
    McpBootstrapResponse,
    McpScopeResolveRequest,
    McpScopeResolveResponse,
    McpSearchRequest,
    McpSearchResponse,
)

router = APIRouter()


@router.post(
    "/bootstrap",
    response_model=McpBootstrapResponse,
    dependencies=[Depends(require_enterprise_service_token)],
)
async def bootstrap_mcp_access(
    body: McpBootstrapRequest,
    db: AsyncSession = Depends(get_db),
):
    service = McpService(db)
    return await service.bootstrap(request=body)


@router.post("/scope/resolve", response_model=McpScopeResolveResponse)
async def resolve_mcp_scope(
    body: McpScopeResolveRequest,
    db: AsyncSession = Depends(get_db),
    auth_context: McpAuthContext = Depends(get_mcp_auth_context),
):
    service = McpService(db, auth_context=auth_context)
    return await service.resolve_scope(
        product_code=body.product_code,
        project_code=body.project_code,
        app_code=body.app_code,
    )


@router.post("/search", response_model=McpSearchResponse)
async def mcp_search(
    body: McpSearchRequest,
    db: AsyncSession = Depends(get_db),
    auth_context: McpAuthContext = Depends(get_mcp_auth_context),
):
    service = McpService(db, auth_context=auth_context)
    return await service.search(request=body)


@router.post("/answer", response_model=McpAnswerResponse)
async def mcp_answer(
    body: McpAnswerRequest,
    db: AsyncSession = Depends(get_db),
    auth_context: McpAuthContext = Depends(get_mcp_auth_context),
):
    service = McpService(db, auth_context=auth_context)
    return await service.answer(request=body)
