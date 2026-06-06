"""Content-risk rule library endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, require_system_admin
from app.application.permission_service import PermissionService
from app.core.authz import PERMISSION_VIEW_QA_LOG
from app.application.content_risk_library_service import ContentRiskLibraryService
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.content_risk_library import (
    ContentRiskLibraryCreate,
    ContentRiskLibraryListResponse,
    ContentRiskLibraryResponse,
    ContentRiskLibraryUpdate,
    ContentRiskLogListResponse,
    ContentRiskLogResponse,
    ContentRiskRuleCreate,
    ContentRiskRuleHitResponse,
    ContentRiskRuleListResponse,
    ContentRiskRuleResponse,
    ContentRiskRuleUpdate,
    ContentRiskTestRequest,
    ContentRiskTestResponse,
)
from app.repositories.content_risk_log_repository import ContentRiskLogRepository
from app.services.content_risk_detection_service import get_content_risk_detection_service

router = APIRouter()


def _build_hit_response(hit: dict) -> ContentRiskRuleHitResponse:
    return ContentRiskRuleHitResponse(
        rule_id=int(hit.get("rule_id") or 0),
        library_id=int(hit.get("library_id") or 0),
        rule_name=str(hit.get("rule_name") or ""),
        risk_category=str(hit.get("risk_category") or ""),
        risk_level=hit.get("risk_level") or "low",
        action=hit.get("action") or "log",
        match_mode=hit.get("match_mode") or "contains",
        pattern=str(hit.get("pattern") or ""),
        matched_text=str(hit.get("matched_text") or ""),
    )


@router.post("/test", response_model=ContentRiskTestResponse)
async def test_content_risk_rules(
    body: ContentRiskTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    del current_user
    result = await get_content_risk_detection_service().check_text(
        scene=body.scene,
        text=body.text,
        db=db,
    )
    return ContentRiskTestResponse(
        scene=result.scene,
        action=result.action,
        blocked=result.blocked,
        risk_level=result.risk_level,
        elapsed_ms=result.elapsed_ms,
        hits=[
            ContentRiskRuleHitResponse(
                rule_id=hit.rule_id,
                library_id=hit.library_id,
                rule_name=hit.rule_name,
                risk_category=hit.risk_category,
                risk_level=hit.risk_level,
                action=hit.action,
                match_mode=hit.match_mode,
                pattern=hit.pattern,
                matched_text=hit.matched_text,
            )
            for hit in result.hits
        ],
    )


@router.get("/logs", response_model=ContentRiskLogListResponse)
async def list_content_risk_logs(
    team_id: int | None = Query(None, description="Optional team filter"),
    scene: str | None = Query(None, description="Optional scene filter"),
    action: str | None = Query(None, description="Optional action filter"),
    blocked: bool | None = Query(None, description="Optional blocked filter"),
    risk_level: str | None = Query(None, description="Optional risk level filter"),
    chat_log_id: int | None = Query(None, description="Optional related chat log id"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Rows per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission_service = PermissionService(db)
    accessible_team_ids = await permission_service.list_accessible_team_ids(current_user)
    if team_id is not None:
        if not await permission_service.has_team_permission(
            current_user, team_id, PERMISSION_VIEW_QA_LOG
        ):
            raise HTTPException(status_code=403, detail="Content risk log permission denied")
        scoped_team_ids = None
    else:
        scoped_team_ids = accessible_team_ids

    rows, total = await ContentRiskLogRepository(db).list_logs(
        page=page,
        page_size=page_size,
        team_id=team_id,
        team_ids=scoped_team_ids,
        scene=scene,
        action=action,
        blocked=blocked,
        risk_level=risk_level,
        chat_log_id=chat_log_id,
    )
    return ContentRiskLogListResponse(
        total=total,
        items=[
            ContentRiskLogResponse(
                id=log.id,
                chat_log_id=log.chat_log_id,
                user_id=log.user_id,
                session_id=log.session_id,
                product_id=log.product_id,
                product_name=product_name,
                project_id=log.project_id,
                project_name=project_name,
                project_app_id=log.project_app_id,
                project_app_name=project_app_name,
                team_id=log.team_id,
                team_name=team_name,
                external_user_id=log.external_user_id,
                external_user_name=log.external_user_name,
                knowledge_base_id=log.knowledge_base_id,
                knowledge_base_name=knowledge_base_name,
                assistant_id=log.assistant_id,
                assistant_name=assistant_name,
                scene=log.scene,
                action=log.action,
                blocked=log.blocked,
                risk_level=log.risk_level,
                matched_text=log.matched_text,
                checked_text=log.checked_text,
                hits=[
                    _build_hit_response(hit)
                    for hit in (log.hits or [])
                    if isinstance(hit, dict)
                ],
                elapsed_ms=log.elapsed_ms,
                created_at=log.created_at,
            )
            for (
                log,
                product_name,
                project_name,
                project_app_name,
                team_name,
                knowledge_base_name,
                assistant_name,
            ) in rows
        ],
    )


@router.get("/libraries", response_model=ContentRiskLibraryListResponse)
async def list_content_risk_libraries(
    keyword: str | None = Query(None, description="Optional keyword"),
    enabled: bool | None = Query(None, description="Optional enabled filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    del current_user
    items = await ContentRiskLibraryService().list_libraries(
        db=db,
        keyword=keyword,
        enabled=enabled,
    )
    return ContentRiskLibraryListResponse(items=items)


@router.post(
    "/libraries",
    response_model=ContentRiskLibraryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_content_risk_library(
    body: ContentRiskLibraryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    return await ContentRiskLibraryService().create_library(
        db=db,
        payload=body,
        actor_user_id=current_user.id,
    )


@router.put("/libraries/{library_id}", response_model=ContentRiskLibraryResponse)
async def update_content_risk_library(
    library_id: int,
    body: ContentRiskLibraryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    return await ContentRiskLibraryService().update_library(
        library_id,
        db=db,
        payload=body,
        actor_user_id=current_user.id,
    )


@router.delete("/libraries/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content_risk_library(
    library_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    await ContentRiskLibraryService().delete_library(
        library_id,
        db=db,
        actor_user_id=current_user.id,
    )


@router.get("/libraries/{library_id}/rules", response_model=ContentRiskRuleListResponse)
async def list_content_risk_rules(
    library_id: int,
    keyword: str | None = Query(None, description="Optional keyword"),
    enabled: bool | None = Query(None, description="Optional enabled filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    del current_user
    items = await ContentRiskLibraryService().list_rules(
        library_id,
        db=db,
        keyword=keyword,
        enabled=enabled,
    )
    return ContentRiskRuleListResponse(items=items)


@router.post(
    "/libraries/{library_id}/rules",
    response_model=ContentRiskRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_content_risk_rule(
    library_id: int,
    body: ContentRiskRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    return await ContentRiskLibraryService().create_rule(
        library_id,
        db=db,
        payload=body,
        actor_user_id=current_user.id,
    )


@router.put("/libraries/{library_id}/rules/{rule_id}", response_model=ContentRiskRuleResponse)
async def update_content_risk_rule(
    library_id: int,
    rule_id: int,
    body: ContentRiskRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    return await ContentRiskLibraryService().update_rule(
        library_id,
        rule_id,
        db=db,
        payload=body,
        actor_user_id=current_user.id,
    )
