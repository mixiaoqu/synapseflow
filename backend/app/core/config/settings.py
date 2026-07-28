"""Application settings loaded from environment variables and .env."""

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .loader import DOTENV_PATH


class Settings(BaseSettings):
    """Environment-backed settings."""

    ENV: str = "development"
    DEBUG: bool = True
    BUSINESS_TIMEZONE: str = "Asia/Shanghai"

    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    MCP_TOKEN_EXPIRE_MINUTES: int = 30
    ENABLE_PUBLIC_REGISTRATION: bool = False
    ENTERPRISE_SERVICE_TOKEN: str = ""
    INTEGRATION_CREDENTIAL_PEPPER: str = ""
    EMBED_TOKEN_EXPIRE_MINUTES: int = 60
    WIDGET_TOKEN_EXPIRE_MINUTES: int = 15
    AGENT_PUBLIC_API_BASE_URL: str = ""
    TOOL_PROVIDER_ALLOWED_HOSTS: str = ""
    EMBED_FRONTEND_BASE_URL: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://synapseflow:password@localhost:5432/synapseflow"
    REDIS_URL: str = "redis://localhost:6379/0"
    DRAMATIQ_INDEXING_QUEUE: str = "indexing"
    DRAMATIQ_GRAPH_INDEXING_QUEUE: str = "graph_indexing"
    DRAMATIQ_EVALUATION_QUEUE: str = "evaluation"
    EMBEDDING_MODEL: Optional[str] = None

    MOYU_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    SILICONFLOW_API_KEY: str = ""

    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_API_URL: str = "https://api.siliconflow.cn/v1/embeddings"
    EMBEDDING_DIMENSIONS: Optional[int] = None
    RERANK_ENABLED: bool = True
    RERANK_PROVIDER: str = "local"
    RERANK_TOP_K: Optional[int] = None
    RERANK_MODEL: Optional[str] = None
    RERANK_API_URL: str = "http://localhost:8012"
    RERANK_API_KEY: str = ""

    GRAPH_ENABLED: bool = False
    GRAPH_INDEXING_ENABLED: bool = False
    GRAPH_URI: str = "bolt://localhost:7687"
    GRAPH_USERNAME: str = "neo4j"
    GRAPH_PASSWORD: str = ""
    GRAPH_DATABASE: str = "neo4j"

    PREVIEW_DIR: str = "./previews"
    UPLOAD_DIR: str = "./uploads"
    DOCUMENT_STAGING_DIR: str = "./uploaded_documents/staging"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024
    OSS_ENABLED: bool = False
    OSS_PROVIDER: str = "volcengine_tos"
    OSS_BUCKET: str = ""
    OSS_ENDPOINT: str = ""
    OSS_REGION: str = ""
    OSS_PUBLIC_ENDPOINT: str = ""
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""
    OSS_UPLOAD_EXPIRE_SECONDS: int = 900

    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: Optional[str] = None
    LANGSMITH_WORKSPACE_ID: Optional[str] = None

    LOG_LEVEL: Optional[str] = None
    LOG_JSON: Optional[bool] = None
    LOG_TO_FILE: Optional[bool] = None
    LOG_DIAGNOSE: Optional[bool] = None

    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _coerce_debug(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return value

    @field_validator("EMBEDDING_DIMENSIONS", "RERANK_TOP_K", mode="before")
    @classmethod
    def _coerce_blank_optional_int(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


settings = Settings()
