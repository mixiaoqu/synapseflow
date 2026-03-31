"""API v1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    collections,
    documents,
    health,
    kb_chat,
    kb_curation,
    prototype_stream,
    revision,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(kb_curation.router, prefix="/kb-curation", tags=["kb-curation"])
api_router.include_router(kb_chat.router, prefix="/kb-chat", tags=["kb-chat"])
api_router.include_router(revision.router, prefix="/revision", tags=["revision"])
api_router.include_router(prototype_stream.router, prefix="/prototype", tags=["prototype"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(collections.router, prefix="/collections", tags=["collections"])
