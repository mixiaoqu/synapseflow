"""Knowledge-base management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.knowledge_base import (
    KnowledgeBaseBranchCreate,
    KnowledgeBaseBranchResponse,
    KnowledgeBaseBranchUpdate,
    KnowledgeBaseCreate,
    KnowledgeBaseRecentDocument,
    KnowledgeBaseResponse,
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
    """Infer a card-friendly status from explicit indexing data."""
    if document_count <= 0:
        return "empty"
    if queued_document_count > 0 or processing_document_count > 0:
        return "indexing"
    if failed_document_count > 0:
        return "error"
    if indexed_document_count > 0 or unindexed_document_count <= 0:
        return "available"
    return "error"


def _normalize_branch_code(code: str) -> str:
    normalized = (code or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Branch code cannot be empty")
    return normalized


def _to_branch_response(record) -> KnowledgeBaseBranchResponse:
    branch = record.branch
    return KnowledgeBaseBranchResponse(
        id=branch.id,
        knowledge_base_id=branch.knowledge_base_id,
        code=branch.code,
        name=branch.name,
        description=branch.description,
        is_active=branch.is_active,
        created_by_user_id=branch.created_by_user_id,
        created_at=branch.created_at,
        updated_at=branch.updated_at,
        bound_app_count=record.bound_app_count,
        document_count=record.document_count,
    )


@router.get("", response_model=list[KnowledgeBaseWithCount])
async def list_knowledge_bases(
    team_id: int | None = Query(None, description="Filter by team id"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    rows = await repo.list_with_count(team_id=team_id)
    return [
        KnowledgeBaseWithCount(
            id=row.knowledge_base.id,
            name=row.knowledge_base.name,
            team_id=row.knowledge_base.team_id,
            description=getattr(row.knowledge_base, "description", None),
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
        for row in rows
    ]


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
        raise HTTPException(status_code=404, detail="Knowledge base not found")
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
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return {"message": "Deleted successfully"}


@router.get("/{knowledge_base_id}/branches", response_model=list[KnowledgeBaseBranchResponse])
async def list_knowledge_base_branches(
    knowledge_base_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    knowledge_base = await repo.get_by_id(knowledge_base_id)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return [_to_branch_response(item) for item in await repo.list_branches(knowledge_base_id)]


@router.post("/{knowledge_base_id}/branches", response_model=KnowledgeBaseBranchResponse)
async def create_knowledge_base_branch(
    knowledge_base_id: int,
    body: KnowledgeBaseBranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    knowledge_base = await repo.get_by_id(knowledge_base_id)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    code = _normalize_branch_code(body.code)
    if await repo.branch_code_exists(knowledge_base_id=knowledge_base_id, code=code):
        raise HTTPException(status_code=400, detail="Branch code already exists")
    branch = await repo.create_branch(
        knowledge_base_id=knowledge_base_id,
        code=code,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
    )
    record = await repo.get_branch_with_counts(branch.id)
    if record is None:
        raise HTTPException(status_code=500, detail="Knowledge base branch creation failed")
    return _to_branch_response(record)


@router.put(
    "/{knowledge_base_id}/branches/{branch_id}",
    response_model=KnowledgeBaseBranchResponse,
)
async def update_knowledge_base_branch(
    knowledge_base_id: int,
    branch_id: int,
    body: KnowledgeBaseBranchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    branch_record = await repo.get_branch_with_counts(branch_id)
    if branch_record is None or branch_record.branch.knowledge_base_id != knowledge_base_id:
        raise HTTPException(status_code=404, detail="Knowledge base branch not found")
    code = _normalize_branch_code(body.code)
    if await repo.branch_code_exists(
        knowledge_base_id=knowledge_base_id,
        code=code,
        exclude_id=branch_id,
    ):
        raise HTTPException(status_code=400, detail="Branch code already exists")
    if not body.is_active and branch_record.bound_app_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Branch is currently bound by project apps and cannot be deactivated",
        )
    await repo.update_branch(
        branch_record.branch,
        code=code,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
    )
    refreshed = await repo.get_branch_with_counts(branch_id)
    if refreshed is None:
        raise HTTPException(status_code=500, detail="Knowledge base branch update failed")
    return _to_branch_response(refreshed)


@router.delete("/{knowledge_base_id}/branches/{branch_id}")
async def delete_knowledge_base_branch(
    knowledge_base_id: int,
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    branch_record = await repo.get_branch_with_counts(branch_id)
    if branch_record is None or branch_record.branch.knowledge_base_id != knowledge_base_id:
        raise HTTPException(status_code=404, detail="Knowledge base branch not found")
    if branch_record.bound_app_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Branch is currently bound by project apps and cannot be deleted",
        )
    if await repo.branch_document_count(branch_id) > 0:
        raise HTTPException(
            status_code=400,
            detail="Branch still has documents and cannot be deleted",
        )
    await repo.delete_branch(branch_record.branch)
    return {"message": "Deleted successfully"}
