"""Knowledge-base management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.application.document_service import document_service
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.knowledge_base import (
    KnowledgeBaseBulkActionFailure,
    KnowledgeBaseBulkActionRequest,
    KnowledgeBaseBulkActionResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseListItem,
    KnowledgeBaseListResponse,
    KnowledgeBaseRecentDocument,
    KnowledgeBaseResponse,
    KnowledgeBaseToggleActive,
    KnowledgeBaseUpdate,
    KnowledgeBaseWithCount,
)
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository

router = APIRouter()


def _resolve_knowledge_base_status(
    *,
    document_count: int,
    indexed_document_count: int,
    queued_document_count: int,
    processing_document_count: int,
    failed_document_count: int,
    unindexed_document_count: int,
) -> str:
    if document_count <= 0:
        return "empty"
    if queued_document_count > 0 or processing_document_count > 0:
        return "indexing"
    if failed_document_count > 0:
        return "error"
    if indexed_document_count > 0 or unindexed_document_count <= 0:
        return "available"
    return "error"


def _build_knowledge_base_with_count(row) -> KnowledgeBaseWithCount:
    item = _build_knowledge_base_list_item(row)
    return KnowledgeBaseWithCount(
        **item.model_dump(),
        recent_documents=[
            KnowledgeBaseRecentDocument(
                id=doc.id,
                title=doc.title,
                document_type=doc.document_type,
                size=doc.size,
                indexed=doc.indexed,
                index_status=doc.index_status,
                index_error=doc.index_error,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
            )
            for doc in row.recent_documents
        ],
    )


def _build_knowledge_base_list_item(row) -> KnowledgeBaseListItem:
    return KnowledgeBaseListItem(
        id=row.knowledge_base.id,
        name=row.knowledge_base.name,
        team_id=row.knowledge_base.team_id,
        description=getattr(row.knowledge_base, "description", None),
        is_active=getattr(row.knowledge_base, "is_active", True),
        created_at=row.knowledge_base.created_at,
        updated_at=row.knowledge_base.updated_at,
        document_count=row.document_count,
        indexed_document_count=row.indexed_document_count,
        queued_document_count=row.queued_document_count,
        processing_document_count=row.processing_document_count,
        failed_document_count=row.failed_document_count,
        unindexed_document_count=row.unindexed_document_count,
        draft_document_count=row.draft_document_count,
        submittable_document_count=row.submittable_document_count,
        pending_review_document_count=row.pending_review_document_count,
        published_document_count=row.published_document_count,
        archived_document_count=row.archived_document_count,
        last_document_updated_at=row.last_document_updated_at,
        last_uploaded_at=row.last_uploaded_at,
        status=_resolve_knowledge_base_status(
            document_count=row.document_count,
            indexed_document_count=row.indexed_document_count,
            queued_document_count=row.queued_document_count,
            processing_document_count=row.processing_document_count,
            failed_document_count=row.failed_document_count,
            unindexed_document_count=row.unindexed_document_count,
        ),
    )


@router.get("", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    team_id: int | None = Query(None, description="Filter by team id"),
    active_only: bool = Query(False, description="Only return active knowledge bases"),
    keyword: str | None = Query(None, description="Search by knowledge-base name or description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    normalized_page = max(1, int(page))
    normalized_page_size = min(100, max(1, int(page_size)))
    total = await repo.count_knowledge_bases(
        team_id=team_id,
        active_only=active_only,
        keyword=keyword,
    )
    rows = await repo.list_with_count(
        team_id=team_id,
        active_only=active_only,
        keyword=keyword,
        offset=(normalized_page - 1) * normalized_page_size,
        limit=normalized_page_size,
    )
    return KnowledgeBaseListResponse(
        items=[_build_knowledge_base_list_item(row) for row in rows],
        total=total,
        page=normalized_page,
        page_size=normalized_page_size,
    )


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    return await repo.create(
        body.name,
        team_id=body.team_id,
        description=body.description,
    )


@router.post("/bulk-actions", response_model=KnowledgeBaseBulkActionResponse)
async def bulk_action_knowledge_bases(
    body: KnowledgeBaseBulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    unique_ids = list(dict.fromkeys(body.knowledge_base_ids))
    failures: list[KnowledgeBaseBulkActionFailure] = []
    affected = 0

    if body.action in {"enable", "disable"}:
        target_active = body.action == "enable"
        changed_items = []
        for knowledge_base_id in unique_ids:
            knowledge_base = await repo.get_by_id(knowledge_base_id)
            if not knowledge_base:
                failures.append(
                    KnowledgeBaseBulkActionFailure(
                        id=knowledge_base_id,
                        message="知识库不存在或无权访问",
                    )
                )
                continue
            knowledge_base.is_active = target_active
            changed_items.append(knowledge_base)
        if changed_items:
            await db.commit()
            affected = len(changed_items)

    elif body.action == "delete":
        for knowledge_base_id in unique_ids:
            ok = await repo.delete(knowledge_base_id)
            if ok:
                affected += 1
            else:
                failures.append(
                    KnowledgeBaseBulkActionFailure(
                        id=knowledge_base_id,
                        message="知识库不存在或无权访问",
                    )
                )

    elif body.action == "reindex":
        for knowledge_base_id in unique_ids:
            knowledge_base = await repo.get_by_id(knowledge_base_id)
            if not knowledge_base:
                failures.append(
                    KnowledgeBaseBulkActionFailure(
                        id=knowledge_base_id,
                        message="知识库不存在或无权访问",
                    )
                )
                continue
            try:
                await document_service.reindex_all_documents(
                    db=db,
                    user_id=current_user.id,
                    knowledge_base_id=knowledge_base_id,
                )
                affected += 1
            except Exception as exc:
                failures.append(
                    KnowledgeBaseBulkActionFailure(
                        id=knowledge_base_id,
                        message=str(exc) or "重建索引任务提交失败",
                    )
                )

    return KnowledgeBaseBulkActionResponse(
        action=body.action,
        total=len(unique_ids),
        affected=affected,
        failed=failures,
    )


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseWithCount)
async def get_knowledge_base(
    knowledge_base_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    rows = await repo.list_with_count(knowledge_base_id=knowledge_base_id, offset=0, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="知识库不存在或无权访问")
    return _build_knowledge_base_with_count(rows[0])


@router.put("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    knowledge_base_id: int,
    body: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    knowledge_base = await repo.update(
        knowledge_base_id,
        name=body.name,
        description=body.description,
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在或无权访问")
    return knowledge_base


@router.patch("/{knowledge_base_id}/toggle-active", response_model=KnowledgeBaseResponse)
async def toggle_knowledge_base_active(
    knowledge_base_id: int,
    body: KnowledgeBaseToggleActive,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    knowledge_base = await repo.get_by_id(knowledge_base_id)
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在或无权访问")
    knowledge_base.is_active = body.is_active
    await db.commit()
    await db.refresh(knowledge_base)
    return knowledge_base


@router.delete("/{knowledge_base_id}")
async def delete_knowledge_base(
    knowledge_base_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    ok = await repo.delete(knowledge_base_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识库不存在或无权访问")
    return {"message": "删除成功"}
