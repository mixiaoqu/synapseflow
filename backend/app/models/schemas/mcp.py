"""Schemas for MCP-specific read-only knowledge access."""

from pydantic import BaseModel, Field


class McpBootstrapRequest(BaseModel):
    product_code: str = Field(..., min_length=1, max_length=120)
    project_code: str = Field(..., min_length=1, max_length=120)
    app_code: str = Field(..., min_length=1, max_length=120)
    client_user_id: str | None = Field(default=None, min_length=1, max_length=255)
    client_user_name: str | None = Field(default=None, max_length=255)
    client_editor: str | None = Field(default=None, max_length=120)
    client_host: str | None = Field(default=None, max_length=255)


class McpScopeSummary(BaseModel):
    product_code: str
    project_code: str
    app_code: str


class McpBootstrapResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    scope: McpScopeSummary


class McpScopeResolveRequest(BaseModel):
    product_code: str = Field(..., min_length=1, max_length=120)
    project_code: str = Field(..., min_length=1, max_length=120)
    app_code: str = Field(..., min_length=1, max_length=120)


class McpBindingItem(BaseModel):
    knowledge_base_id: int
    knowledge_base_name: str | None = None
    knowledge_base_branch_id: int | None = None
    knowledge_base_branch_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None


class McpScopeResolveResponse(BaseModel):
    team_id: int
    product_id: int
    product_code: str
    product_name: str
    project_id: int
    project_code: str
    project_name: str
    project_app_id: int
    app_code: str
    app_name: str
    assistant_id: int | None = None
    assistant_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    knowledge_base_ids: list[int] = Field(default_factory=list)
    knowledge_base_branch_ids: list[int] = Field(default_factory=list)
    bindings: list[McpBindingItem] = Field(default_factory=list)


class McpSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    product_code: str = Field(..., min_length=1, max_length=120)
    project_code: str = Field(..., min_length=1, max_length=120)
    app_code: str = Field(..., min_length=1, max_length=120)
    top_k: int = Field(default=6, ge=1, le=20)


class McpSearchItem(BaseModel):
    content: str
    document_id: int
    document_title: str | None = None
    knowledge_base_id: int | None = None
    knowledge_base_branch_id: int | None = None
    section_path: str | None = None
    score: float | None = None
    rerank_score: float | None = None


class McpSearchResponse(BaseModel):
    items: list[McpSearchItem] = Field(default_factory=list)


class McpAnswerRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    product_code: str = Field(..., min_length=1, max_length=120)
    project_code: str = Field(..., min_length=1, max_length=120)
    app_code: str = Field(..., min_length=1, max_length=120)
    session_id: str | None = Field(default=None, max_length=64)


class McpAnswerResponse(BaseModel):
    answer: str
    answer_status: str
    retrieved_docs: list[dict] = Field(default_factory=list)
