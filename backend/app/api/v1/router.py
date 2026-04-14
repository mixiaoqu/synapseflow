"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    ask,
    auth,
    document_categories,
    documents,
    health,
    kb_chat,
    kb_curation,
    knowledge_bases,
    prototype_stream,
    revision,
    sensitive_words,
    teams,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(ask.router, prefix="/ask", tags=["ask"])
api_router.include_router(ask.admin_router, prefix="/admin/qa", tags=["admin-qa"])
api_router.include_router(kb_curation.router, prefix="/kb-curation", tags=["kb-curation"])
api_router.include_router(kb_chat.router, prefix="/kb-chat", tags=["kb-chat"])
api_router.include_router(revision.router, prefix="/revision", tags=["revision"])
api_router.include_router(prototype_stream.router, prefix="/prototype", tags=["prototype"])
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
