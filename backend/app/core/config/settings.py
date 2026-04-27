"""Application settings loaded from environment variables and .env."""

from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .loader import DOTENV_PATH


class Settings(BaseSettings):
    """Environment-backed settings."""

    ENV: str = "development"
    DEBUG: bool = True

    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ENABLE_PUBLIC_REGISTRATION: bool = False
    ENTERPRISE_SERVICE_TOKEN: str = ""
    EMBED_TOKEN_EXPIRE_MINUTES: int = 15
    EMBED_FRONTEND_BASE_URL: str = ""

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    DATABASE_URL: str = "postgresql+asyncpg://synapseflow:password@localhost:5432/synapseflow"
    REDIS_URL: str = "redis://localhost:6379/0"
    DRAMATIQ_INDEXING_QUEUE: str = "indexing"
    EMBEDDING_MODEL: Optional[str] = None

    MOYU_API_KEY: str = ""

    RERANK_ENABLED: bool = True
    RERANK_PROVIDER: str = "local"
    RERANK_TOP_K: Optional[int] = None
    RERANK_API_URL: str = "http://localhost:8012"
    RERANK_API_KEY: str = ""

    PREVIEW_DIR: str = "./previews"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024

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

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        """Return parsed CORS origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

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


settings = Settings()
