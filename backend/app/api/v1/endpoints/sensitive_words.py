"""Sensitive-word management API."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_any_admin_role, require_kb_admin_role
from app.db.models import SensitiveWord, User
from app.db.session import get_db
from app.models.schemas.sensitive_word import (
    SensitiveWordCheckRequest,
    SensitiveWordCheckResponse,
    SensitiveWordCreate,
    SensitiveWordImportRequest,
    SensitiveWordImportResponse,
    SensitiveWordListResponse,
    SensitiveWordResponse,
    SensitiveWordSettingsResponse,
    SensitiveWordSettingsUpdate,
    SensitiveWordUpdate,
)
from app.repositories.team_repository import TeamRepository
from app.services.sensitive_word_service import get_sensitive_word_service

router = APIRouter()


def _serialize_word(row: SensitiveWord) -> SensitiveWordResponse:
    return SensitiveWordResponse.model_validate(row)


async def _ensure_team_exists(
    *,
    db: AsyncSession,
    current_user: User,
    team_id: int | None,
) -> None:
    if team_id is None:
        return
    team = await TeamRepository(db, user_id=current_user.id).get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")


@router.get("/settings", response_model=SensitiveWordSettingsResponse)
async def get_sensitive_word_settings(
    team_id: int | None = Query(None, description="Null means the global scope"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    await _ensure_team_exists(db=db, current_user=current_user, team_id=team_id)
    payload = await get_sensitive_word_service().get_scoped_settings(team_id=team_id, db=db)
    return SensitiveWordSettingsResponse(**payload)


@router.put("/settings", response_model=SensitiveWordSettingsResponse)
async def update_sensitive_word_settings(
    body: SensitiveWordSettingsUpdate,
    team_id: int | None = Query(None, description="Null means the global scope"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_kb_admin_role),
):
    await _ensure_team_exists(db=db, current_user=current_user, team_id=team_id)
    row = await get_sensitive_word_service().update_scoped_settings(
        team_id=team_id,
        enabled=body.enabled,
        block_query=body.block_query,
        block_document_publish=body.block_document_publish,
        actor_user_id=current_user.id,
        db=db,
    )
    return SensitiveWordSettingsResponse.model_validate(row)


@router.get("", response_model=SensitiveWordListResponse)
async def list_sensitive_words(
    team_id: int | None = Query(None, description="Null means the global scope"),
    keyword: str | None = Query(None, description="Optional keyword"),
    enabled: bool | None = Query(None, description="Optional enabled filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    await _ensure_team_exists(db=db, current_user=current_user, team_id=team_id)
    rows, total, enabled_count, disabled_count = await get_sensitive_word_service().list_words_paginated(
        team_id=team_id,
        keyword=keyword,
        enabled=enabled,
        page=page,
        page_size=page_size,
        db=db,
    )
    return SensitiveWordListResponse(
        items=[_serialize_word(row) for row in rows],
        total=total,
        enabled_count=enabled_count,
        disabled_count=disabled_count,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SensitiveWordResponse, status_code=status.HTTP_201_CREATED)
async def create_sensitive_word(
    body: SensitiveWordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_kb_admin_role),
):
    await _ensure_team_exists(db=db, current_user=current_user, team_id=body.team_id)
    try:
        row = await get_sensitive_word_service().create_word(
            team_id=body.team_id,
            word=body.word,
            category=body.category,
            enabled=body.enabled,
            remark=body.remark,
            actor_user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize_word(row)


@router.put("/{word_id}", response_model=SensitiveWordResponse)
async def update_sensitive_word(
    word_id: int,
    body: SensitiveWordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_kb_admin_role),
):
    try:
        row = await get_sensitive_word_service().update_word(
            word_id,
            word=body.word,
            category=body.category,
            enabled=body.enabled,
            remark=body.remark,
            actor_user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Sensitive word not found")
    return _serialize_word(row)


@router.delete("/{word_id}")
async def delete_sensitive_word(
    word_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_kb_admin_role),
):
    del current_user
    ok = await get_sensitive_word_service().delete_word(word_id, db=db)
    if not ok:
        raise HTTPException(status_code=404, detail="Sensitive word not found")
    return {"message": "Deleted successfully"}


@router.post("/import", response_model=SensitiveWordImportResponse)
async def import_sensitive_words(
    body: SensitiveWordImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_kb_admin_role),
):
    await _ensure_team_exists(db=db, current_user=current_user, team_id=body.team_id)
    rows, skipped_count = await get_sensitive_word_service().import_words(
        team_id=body.team_id,
        words_text=body.words_text,
        category=body.category,
        enabled=body.enabled,
        actor_user_id=current_user.id,
        db=db,
    )
    return SensitiveWordImportResponse(
        created_count=len(rows),
        skipped_count=skipped_count,
        items=[_serialize_word(row) for row in rows],
    )


@router.post("/check", response_model=SensitiveWordCheckResponse)
async def check_sensitive_words(
    body: SensitiveWordCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_admin_role),
):
    await _ensure_team_exists(db=db, current_user=current_user, team_id=body.team_id)
    result = await get_sensitive_word_service().check_text(
        scene=body.scene,
        text=body.text,
        team_id=body.team_id,
        db=db,
    )
    return SensitiveWordCheckResponse(
        blocked=result.blocked,
        matched_words=result.matched_words,
        scene=result.scene,
        reason=result.reason,
    )
