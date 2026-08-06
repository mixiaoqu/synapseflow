"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    assistants,
    auth,
    content_risk_libraries,
    document_categories,
    documents,
    evaluations,
    health,
    integration_bootstrap,
    knowledge_bases,
    products,
    project_app_access,
    projects,
    qa_review,
    teams,
    tool_providers,
    users,
    widget,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(qa_review.router, prefix="/admin/qa", tags=["admin-qa"])
api_router.include_router(widget.router, prefix="/widget", tags=["widget"])
api_router.include_router(
    integration_bootstrap.router,
    prefix="/integration",
    tags=["integration"],
)
api_router.include_router(assistants.router, prefix="/assistants", tags=["assistants"])
api_router.include_router(project_app_access.router, prefix="/agent-integrations", tags=["agent-integrations"])
api_router.include_router(tool_providers.router, prefix="/agent-integrations", tags=["agent-integrations"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(
    document_categories.router,
    prefix="/document-categories",
    tags=["document-categories"],
)
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(
    content_risk_libraries.router,
    prefix="/content-risk",
    tags=["content-risk"],
)
api_router.include_router(
    knowledge_bases.router,
    prefix="/knowledge-bases",
    tags=["knowledge-bases"],
)
api_router.include_router(
    evaluations.router,
    prefix="/evaluations",
    tags=["evaluations"],
)
