"""
应用配置：仅负责 .env 环境变量
使用 pydantic-settings 加载和校验
"""
from typing import Optional, List

from pydantic_settings import BaseSettings, SettingsConfigDict

from .loader import DOTENV_PATH


class Settings(BaseSettings):
    """环境变量配置（.env）"""

    # --- 基础元数据 ---
    PROJECT_NAME: str = "SynapseFlow"
    VERSION: str = "0.1.0"
    ENV: str = "development"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # --- 安全配置 ---
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1天

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        """解析CORS_ORIGINS为列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # --- 数据库 ---
    DATABASE_URL: str = "postgresql+asyncpg://synapseflow:password@localhost:5432/synapseflow"

    # --- LLM API密钥配置 ---
    DEEPSEEK_API_KEY: str = ""
    KIMI_API_KEY: str = ""
    SILICONFLOW_API_KEY: str = ""
    MODELSCOPE_API_KEY: str = ""
    AIHUBMIX_API_KEY: str = ""

    # --- 向量数据库配置（本地 BGE 中文嵌入）---
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    VECTOR_DIMENSION: int = 1024

    # --- 阿里云百炼（DashScope）---
    DASHSCOPE_API_KEY: str = ""

    # --- 墨鱼（OpenAI 兼容，config/models.yaml provider moyu）---
    MOYU_API_KEY: str = ""

    # --- Rerank 远程 API：bailian=阿里云百炼，vllm=自建 vLLM（与无距离阈值的向量召回配合）---
    RERANK_ENABLED: bool = True
    RERANK_PROVIDER: str = "bailian"  # bailian | vllm
    RERANK_API_URL: str = "http://localhost:8012"  # vllm 时使用
    RERANK_API_KEY: str = ""  # vllm 时可选
    RERANK_MODEL: str = "qwen3-rerank"  # bailian 固定；vllm 可配置
    # 检索条数见 config/embedding.yaml retrieval.final_top_k；交给生成模型的条数可设 llm_reference_top_k
    RERANK_INSTRUCT: str = "Given a web search query, retrieve relevant passages that answer the query."

    # --- 文件存储配置 ---
    PREVIEW_DIR: str = "./previews"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    # --- LangSmith 可观测性 ---
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: Optional[str] = None
    LANGSMITH_WORKSPACE_ID: Optional[str] = None

    # --- 日志配置（优先于 config/logging.yaml）---
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


settings = Settings()
