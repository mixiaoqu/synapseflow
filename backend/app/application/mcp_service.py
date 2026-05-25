"""Application service for MCP read-only knowledge access."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.mcp_auth import McpAuthContext, McpTokenContext
from app.application.kb_chat_service import get_kb_chat_service
from app.core.config import settings
from app.core.security import create_mcp_token
from app.models.schemas.mcp import (
    McpBootstrapRequest,
    McpBootstrapResponse,
    McpAnswerRequest,
    McpAnswerResponse,
    McpBindingItem,
    McpScopeSummary,
    McpScopeResolveResponse,
    McpSearchRequest,
    McpSearchResponse,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.team_repository import TeamRepository
from app.services.kb_text_retrieval import run_multi_query_kb_text_retrieval


class McpService:
    """Resolve MCP product scope and proxy read-only KB operations."""

    def __init__(self, db: AsyncSession, *, auth_context: McpAuthContext | None = None):
        self.db = db
        self.auth_context = auth_context
        self.project_repository = ProjectRepository(db)
        self.team_repository = (
            TeamRepository(db, user_id=auth_context.user.id)
            if auth_context is not None and auth_context.user is not None
            else None
        )

    @property
    def user_id(self) -> int | None:
        if self.auth_context is None or self.auth_context.user is None:
            return None
        return int(self.auth_context.user.id)

    @property
    def mcp_token(self) -> McpTokenContext | None:
        return self.auth_context.mcp_token if self.auth_context is not None else None

    def _build_scope_response(self, runtime) -> McpScopeResolveResponse:
        bindings = [
            McpBindingItem(
                knowledge_base_id=item.knowledge_base_id,
                knowledge_base_name=item.knowledge_base_name,
                knowledge_base_branch_id=None,
                knowledge_base_branch_name=None,
            )
            for item in runtime.bindings
        ]
        knowledge_base_ids = [item.knowledge_base_id for item in runtime.bindings]
        assistant = runtime.assistant
        return McpScopeResolveResponse(
            team_id=runtime.project.team_id,
            product_id=runtime.product.id,
            product_code=runtime.product.code,
            product_name=runtime.product.name,
            project_id=runtime.project.id,
            project_code=runtime.project.code,
            project_name=runtime.project.name,
            project_app_id=runtime.app.id,
            app_code=runtime.app.code,
            app_name=runtime.app.name,
            assistant_id=assistant.id if assistant is not None else None,
            assistant_name=assistant.name if assistant is not None else None,
            knowledge_base_ids=knowledge_base_ids,
            knowledge_base_branch_ids=[],
            bindings=bindings,
        )

    def _assert_token_matches_scope(
        self,
        *,
        token: McpTokenContext,
        product_code: str,
        project_code: str,
        app_code: str,
    ) -> None:
        requested = (
            self.project_repository.normalize_code(product_code),
            self.project_repository.normalize_code(project_code),
            self.project_repository.normalize_code(app_code),
        )
        expected = (
            self.project_repository.normalize_code(token.product_code),
            self.project_repository.normalize_code(token.project_code),
            self.project_repository.normalize_code(token.app_code),
        )
        if requested != expected:
            raise HTTPException(status_code=403, detail="MCP token scope mismatch")

    async def bootstrap(self, *, request: McpBootstrapRequest) -> McpBootstrapResponse:
        runtime = await self.project_repository.get_runtime_by_codes(
            product_code=request.product_code,
            project_code=request.project_code,
            app_code=request.app_code,
            active_only=True,
        )
        if runtime is None:
            raise HTTPException(status_code=404, detail="Active project application not found")

        scope = self._build_scope_response(runtime)
        expires_in_minutes = max(1, settings.MCP_TOKEN_EXPIRE_MINUTES)
        client_user_id = (request.client_user_id or "").strip() or "unknown-user"
        client_user_name = (request.client_user_name or "").strip() or None
        client_editor = (request.client_editor or "").strip() or None
        client_host = (request.client_host or "").strip() or None
        access_token = create_mcp_token(
            product_id=scope.product_id,
            project_id=scope.project_id,
            project_app_id=scope.project_app_id,
            product_code=scope.product_code,
            project_code=scope.project_code,
            app_code=scope.app_code,
            client_user_id=client_user_id,
            client_user_name=client_user_name,
            client_editor=client_editor,
            client_host=client_host,
            expires_delta=timedelta(minutes=expires_in_minutes),
        )
        return McpBootstrapResponse(
            access_token=access_token,
            expires_in_seconds=expires_in_minutes * 60,
            scope=McpScopeSummary(
                product_code=scope.product_code,
                project_code=scope.project_code,
                app_code=scope.app_code,
            ),
        )

    async def resolve_scope(
        self,
        *,
        product_code: str,
        project_code: str,
        app_code: str,
    ) -> McpScopeResolveResponse:
        token = self.mcp_token
        if token is not None:
            self._assert_token_matches_scope(
                token=token,
                product_code=product_code,
                project_code=project_code,
                app_code=app_code,
            )
            runtime = await self.project_repository.get_runtime_by_app_id(
                project_app_id=token.project_app_id,
                active_only=True,
            )
            if runtime is None or runtime.project.id != token.project_id:
                raise HTTPException(status_code=404, detail="Active project application not found")
            return self._build_scope_response(runtime)

        runtime = await self.project_repository.get_runtime_by_codes(
            product_code=product_code,
            project_code=project_code,
            app_code=app_code,
            active_only=True,
        )
        if runtime is None:
            raise HTTPException(status_code=404, detail="Active project application not found")

        if self.team_repository is None:
            raise HTTPException(status_code=401, detail="Authentication required")

        if not await self.team_repository.can_access_team(runtime.project.team_id):
            raise HTTPException(status_code=403, detail="Team access denied")

        return self._build_scope_response(runtime)

    async def search(self, *, request: McpSearchRequest) -> McpSearchResponse:
        scope = await self.resolve_scope(
            product_code=request.product_code,
            project_code=request.project_code,
            app_code=request.app_code,
        )
        if len(scope.knowledge_base_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="MCP search currently supports exactly one bound knowledge base",
            )
        knowledge_base_id = (
            scope.knowledge_base_ids[0] if len(scope.knowledge_base_ids) == 1 else None
        )
        retrieval = await run_multi_query_kb_text_retrieval(
            query=request.query,
            retrieval_queries=[request.query],
            team_id=scope.team_id,
            knowledge_base_id=knowledge_base_id,
            user_id=self.user_id,
            result_limit=request.top_k,
        )
        items = []
        for doc in retrieval.get("retrieved_docs", []):
            metadata = dict(doc.get("metadata") or {})
            items.append(
                {
                    "content": str(doc.get("content") or ""),
                    "document_id": int(metadata.get("document_id") or 0),
                    "document_title": metadata.get("document_title"),
                    "knowledge_base_id": metadata.get("knowledge_base_id"),
                    "knowledge_base_branch_id": metadata.get("knowledge_base_branch_id"),
                    "section_path": metadata.get("section_path"),
                    "score": metadata.get("score"),
                    "rerank_score": metadata.get("rerank_score"),
                }
            )
        return McpSearchResponse(items=items)

    async def answer(self, *, request: McpAnswerRequest) -> McpAnswerResponse:
        scope = await self.resolve_scope(
            product_code=request.product_code,
            project_code=request.project_code,
            app_code=request.app_code,
        )
        if len(scope.knowledge_base_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="MCP answer currently supports exactly one bound knowledge base",
            )
        runtime_request = SimpleNamespace(
            query=request.query,
            session_id=None,
            team_id=scope.team_id,
            product_id=scope.product_id,
            project_id=scope.project_id,
            project_app_id=scope.project_app_id,
            knowledge_base_id=(
                scope.knowledge_base_ids[0] if len(scope.knowledge_base_ids) == 1 else None
            ),
            knowledge_base_ids=list(scope.knowledge_base_ids),
            knowledge_base_branch_ids=[],
        )
        response = await get_kb_chat_service().preview(runtime_request, user_id=self.user_id)
        return McpAnswerResponse(
            answer=response.answer,
            answer_status=response.answer_status,
            retrieved_docs=list(response.retrieved_docs or []),
        )
