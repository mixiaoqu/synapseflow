"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    assistants,
    ask,
    auth,
    agent_integrations,
    content_risk_libraries,
    document_categories,
    documents,
    embed,
    evaluations,
    health,
    knowledge_bases,
    mcp,
    products,
    projects,
    teams,
    users,
    widget,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(ask.router, prefix="/ask", tags=["ask"])
api_router.include_router(ask.admin_router, prefix="/admin/qa", tags=["admin-qa"])
api_router.include_router(embed.router, prefix="/embed", tags=["embed"])
api_router.include_router(widget.router, prefix="/widget", tags=["widget"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
api_router.include_router(assistants.router, prefix="/assistants", tags=["assistants"])
api_router.include_router(agent_integrations.router, prefix="/agent-integrations", tags=["agent-integrations"])
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
