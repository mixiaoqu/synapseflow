"""Business-backend bootstrap exchange for the Agent Loader."""

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.integration_bootstrap_service import IntegrationBootstrapService
from app.core.config import settings
from app.db.session import get_db
from app.models.schemas.widget import (
    IntegrationBootstrapCreate,
    IntegrationBootstrapResponse,
    IntegrationWidgetConfig,
)

router = APIRouter()
client_basic_scheme = HTTPBasic()


@router.post("/bootstrap", response_model=IntegrationBootstrapResponse)
async def create_integration_bootstrap(
    body: IntegrationBootstrapCreate,
    request: Request,
    credentials: HTTPBasicCredentials = Depends(client_basic_scheme),
    db: AsyncSession = Depends(get_db),
):
    issued = await IntegrationBootstrapService(db).create_bootstrap(
        client_id=credentials.username,
        client_secret=credentials.password,
        payload=body,
    )
    configured_api_base_url = settings.AGENT_PUBLIC_API_BASE_URL.strip().rstrip("/")
    api_base_url = configured_api_base_url or f"{str(request.base_url).rstrip('/')}/api/v1"
    return IntegrationBootstrapResponse(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        api_base_url=api_base_url,
        widget=IntegrationWidgetConfig(version=issued.widget_version),
    )
