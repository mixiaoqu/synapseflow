"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    assistants,
    ask,
    auth,
    document_categories,
    documents,
    health,
    knowledge_bases,
    sensitive_words,
    teams,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(ask.router, prefix="/ask", tags=["ask"])
api_router.include_router(ask.admin_router, prefix="/admin/qa", tags=["admin-qa"])
api_router.include_router(assistants.router, prefix="/assistants", tags=["assistants"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(
    document_categories.router,
    prefix="/document-categories",
    tags=["document-categories"],
)
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(
    sensitive_words.router,
    prefix="/sensitive-words",
    tags=["sensitive-words"],
)
api_router.include_router(
    knowledge_bases.router,
    prefix="/knowledge-bases",
    tags=["knowledge-bases"],
)
