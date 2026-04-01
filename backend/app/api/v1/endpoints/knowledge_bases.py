"""Knowledge-base management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeBaseWithCount,
)
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository

router = APIRouter()


@router.get("", response_model=list[KnowledgeBaseWithCount])
async def list_knowledge_bases(
    team_id: int | None = Query(None, description="Filter by team id"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    rows = await repo.list_with_count(team_id=team_id)
    return [
        KnowledgeBaseWithCount(
            id=knowledge_base.id,
            name=knowledge_base.name,
            team_id=knowledge_base.team_id,
            description=getattr(knowledge_base, "description", None),
            created_at=knowledge_base.created_at,
            updated_at=knowledge_base.updated_at,
            document_count=doc_count,
        )
        for knowledge_base, doc_count in rows
    ]


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    ok = await repo.delete(knowledge_base_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return {"message": "Deleted successfully"}
