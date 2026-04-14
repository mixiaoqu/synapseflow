"""Document-category management API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.document_category import (
    DocumentCategoryCreate,
    DocumentCategoryResponse,
    DocumentCategoryUpdate,
)
from app.repositories.document_category_repository import DocumentCategoryRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository

router = APIRouter()


@router.get("", response_model=list[DocumentCategoryResponse])
async def list_document_categories(
    knowledge_base_id: int = Query(..., description="Owning knowledge base id"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = DocumentCategoryRepository(db, user_id=current_user.id)
    rows = await repo.list_for_knowledge_base(knowledge_base_id)
    return [
        DocumentCategoryResponse(
            id=row.category.id,
            knowledge_base_id=row.category.knowledge_base_id,
            name=row.category.name,
            document_count=row.document_count,
            created_at=row.category.created_at,
            updated_at=row.category.updated_at,
        )
        for row in rows
    ]


@router.post("", response_model=DocumentCategoryResponse)
async def create_document_category(
    body: DocumentCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    kb_repo = KnowledgeBaseRepository(db, user_id=current_user.id)
    knowledge_base = await kb_repo.get_by_id(body.knowledge_base_id)
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    repo = DocumentCategoryRepository(db, user_id=current_user.id)
    existing = await repo.get_by_name(
        knowledge_base_id=body.knowledge_base_id,
        name=body.name,
    )
    category = existing or await repo.create(
        knowledge_base_id=body.knowledge_base_id,
        name=body.name,
    )
    return DocumentCategoryResponse(
        id=category.id,
        knowledge_base_id=category.knowledge_base_id,
        name=category.name,
        document_count=0,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.put("/{category_id}", response_model=DocumentCategoryResponse)
async def update_document_category(
    category_id: int,
    body: DocumentCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = DocumentCategoryRepository(db, user_id=current_user.id)
    category = await repo.get_by_id(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    duplicate = await repo.get_by_name(
        knowledge_base_id=category.knowledge_base_id,
        name=body.name,
    )
    if duplicate and duplicate.id != category_id:
        raise HTTPException(status_code=400, detail="Category name already exists")

    category = await repo.update(category_id, name=body.name)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return DocumentCategoryResponse(
        id=category.id,
        knowledge_base_id=category.knowledge_base_id,
        name=category.name,
        document_count=0,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.delete("/{category_id}")
async def delete_document_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = DocumentCategoryRepository(db, user_id=current_user.id)
    ok = await repo.delete(category_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Deleted successfully"}
