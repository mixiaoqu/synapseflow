"""Remote Streamable HTTP MCP transport for the Agent entrypoint."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

from app.application.remote_mcp_service import (
    RemoteMcpAuthenticationError,
    RemoteMcpConfigurationError,
    RemoteMcpContext,
    authenticate_remote_mcp,
    chat_remote_mcp,
)
from app.db.session import AsyncSessionLocal


@dataclass(frozen=True, slots=True)
class _RequestState:
    context: RemoteMcpContext


_request_state: ContextVar[_RequestState | None] = ContextVar(
    "remote_mcp_request_state",
    default=None,
)


def _header(scope: dict[str, Any], name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1").strip() or None
    return None


def _bearer_token(scope: dict[str, Any]) -> str:
    authorization = _header(scope, b"authorization") or ""
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise RemoteMcpAuthenticationError("Bearer authentication is required")
    return token.strip()


class RemoteMcpAuthMiddleware:
    """Authenticate every MCP HTTP message before it reaches the protocol server."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        try:
            bearer_token = _bearer_token(scope)
            mcp_session_id = _header(scope, b"mcp-session-id")
            async with AsyncSessionLocal() as db:
                context = await authenticate_remote_mcp(
                    db,
                    bearer_token=bearer_token,
                    mcp_session_id=mcp_session_id,
                )
        except RemoteMcpConfigurationError as exc:
            response = JSONResponse({"detail": str(exc)}, status_code=409)
            await response(scope, receive, send)
            return
        except RemoteMcpAuthenticationError as exc:
            response = JSONResponse({"detail": str(exc)}, status_code=401)
            await response(scope, receive, send)
            return

        state_token: Token[_RequestState | None] = _request_state.set(
            _RequestState(context=context)
        )
        try:
            await self.app(scope, receive, send)
        finally:
            _request_state.reset(state_token)


class McpPathMiddleware:
    """Normalize the public MCP URL so clients may use /mcp without a slash."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
            scope["raw_path"] = b"/mcp/"
        await self.app(scope, receive, send)


def _current_context() -> RemoteMcpContext:
    state = _request_state.get()
    if state is None:
        raise RuntimeError("MCP request context is unavailable")
    return state.context


mcp_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "zsk.szsayu.com"
    ],
)


mcp_server = FastMCP(
    "SynapseFlow Agent",
    instructions=(
        "通过当前应用绑定的知识库回答问题，回答仅基于检索到的知识库证据。"
    ),
    stateless_http=False,
    json_response=True,
    transport_security=mcp_transport_security,
)
mcp_server.settings.streamable_http_path = "/"


@mcp_server.tool()
async def agent_chat(message: str) -> dict[str, Any]:
    """通过当前应用授权的主 Agent 回答一个问题。"""

    context = _current_context()
    response = await chat_remote_mcp(context, message=message)
    sources = []
    for document in list(response.retrieved_docs or []):
        metadata = dict(document.get("metadata") or {})
        sources.append(
            {
                "source_path": metadata.get("source_path"),
                "language": metadata.get("language"),
                "start_line": metadata.get("start_line"),
                "end_line": metadata.get("end_line"),
                "content": str(document.get("content") or ""),
                "document_id": metadata.get("document_id"),
                "document_title": metadata.get("document_title"),
                "section_path": metadata.get("section_path"),
                "document_chunk_id": metadata.get("document_chunk_id"),
                "parent_chunk_id": metadata.get("parent_chunk_id"),
            }
        )
    return {
        "answer": response.answer,
        "answer_status": response.answer_status,
        "sources": sources,
    }


mcp_http_app = RemoteMcpAuthMiddleware(mcp_server.streamable_http_app())
