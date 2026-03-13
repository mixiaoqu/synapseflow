"""API v1路由聚合"""
from fastapi import APIRouter

from app.api.v1.endpoints import health, qa, revision, prototype_stream, documents

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(qa.router, prefix="/qa", tags=["qa"])
api_router.include_router(revision.router, prefix="/revision", tags=["revision"])
api_router.include_router(prototype_stream.router, prefix="/prototype", tags=["prototype"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
