"""
Configuration registry: owns parsed config objects.
Uses the loader to read raw data, then exposes typed accessors for
business-facing configuration.
"""

import functools
from typing import Any, Dict

from .loader import (
    load_app_raw,
    load_embedding_raw,
    load_logging_raw,
    load_models_raw,
    load_rerank_raw,
    load_repositories_raw,
)
from .schemas import (
    AppConfig,
    EmbeddingConfig,
    IndexingBatchConfig,
    LoggingConfig,
    LoggingFileConfig,
    ModelConfig,
    RagChunkConfig,
    RagConfig,
    RagEvaluateConfig,
    RagEvaluateWeights,
    RagRetrievalConfig,
    RerankConfig,
)
from .settings import settings


class ConfigRegistry:
    """Provides parsed, cached configuration objects."""

    @functools.lru_cache(maxsize=1)
    def get_app_config(self) -> AppConfig:
        """Get application-level settings from `config/app.yaml`."""
        data = load_app_raw()
        app = data.get("app", {}) or {}
        return AppConfig(
            project_name=app.get("project_name", "SynapseFlow"),
            version=app.get("version", "0.1.0"),
            description=app.get("description", "基于 LangGraph 的智能体协同系统"),
            api_v1_str=app.get("api_v1_str", "/api/v1"),
        )

    @functools.lru_cache(maxsize=None)
    def get_model_config(self, model_type: str) -> ModelConfig:
        """Get the model config for a given logical model type."""
        data = load_models_raw()
        models_cfg = data.get("models", {})
        providers_cfg = data.get("providers", {})
        api_keys_mapping = data.get("api_keys", {})

        raw = models_cfg.get(model_type, {})
        if not raw:
            raise ValueError(f"模型类型 '{model_type}' 未在 models.yaml 中定义")

        provider_id = raw.get("provider")
        if not provider_id:
            raise ValueError(f"模型 '{model_type}' 缺少 provider 配置")

        provider = providers_cfg.get(provider_id, {})
        if not provider:
            raise ValueError(f"Provider '{provider_id}' 未在 providers 中定义")

        api_key_env_name = api_keys_mapping.get(provider_id)
        api_key = getattr(settings, api_key_env_name, "").strip() if api_key_env_name else ""

        if not api_key:
            raise ValueError(
                f"Provider '{provider_id}' 的 API 密钥未配置"
                f"（环境变量: {api_key_env_name}）"
            )

        return ModelConfig(
            model=raw.get("model", "gpt-4"),
            name=raw.get("name", model_type),
            api_key=api_key,
            api_base=provider.get("api_base", ""),
            temperature=float(raw.get("temperature", 0.7)),
            request_timeout=int(raw.get("request_timeout", 120)),
            streaming=bool(raw.get("streaming", True)),
            max_tokens=int(raw["max_tokens"]) if raw.get("max_tokens") is not None else None,
        )

    @functools.lru_cache(maxsize=1)
    def get_embedding_config(self) -> EmbeddingConfig:
        """Get embedding config from `config/embedding.yaml`."""
        data = load_embedding_raw()
        emb = data.get("embedding", {})
        model_override = (settings.EMBEDDING_MODEL or "").strip()
        return EmbeddingConfig(
            model=model_override or emb.get("model", "BAAI/bge-m3"),
            dim=int(emb.get("dim", 1024)),
            device=str(emb.get("device", "cpu")),
            batch_size=max(1, int(emb.get("batch_size", 32))),
        )

    @functools.lru_cache(maxsize=1)
    def get_indexing_batch_config(self) -> IndexingBatchConfig:
        """Get dynamic multi-document indexing batch config from `config/embedding.yaml`."""
        data = load_embedding_raw()
        batch = data.get("indexing_batch", {}) or {}
        return IndexingBatchConfig(
            max_docs=max(1, int(batch.get("max_docs", 8))),
            max_chunks=max(1, int(batch.get("max_chunks", 256))),
            max_chars=max(1, int(batch.get("max_chars", 200_000))),
        )

    @functools.lru_cache(maxsize=1)
    def get_rag_config(self) -> RagConfig:
        """
        Get RAG-related config including chunking, retrieval, and evaluation.
        All values come from `config/embedding.yaml` and are cached in-process.
        """
        data = load_embedding_raw()
        chunk = data.get("chunk", {}) or {}
        retrieval = data.get("retrieval", {}) or {}
        ev = data.get("evaluate", {}) or {}
        w = ev.get("weights", {}) or {}
        wr = float(w.get("relevance", 0.25))
        wg = float(w.get("groundedness", 0.45))
        wc = float(w.get("completeness", 0.30))
        total = wr + wg + wc
        if total > 0 and abs(total - 1.0) > 1e-6:
            wr, wg, wc = wr / total, wg / total, wc / total

        return RagConfig(
            chunk=RagChunkConfig(
                size=int(chunk.get("size", 700)),
                overlap=int(chunk.get("overlap", 100)),
            ),
            retrieval=RagRetrievalConfig(
                k_first=int(retrieval.get("k_first", 16)),
                k_iteration=int(retrieval.get("k_iteration", 20)),
                distance_threshold=float(retrieval.get("distance_threshold", 0.5)),
                distance_threshold_iteration=float(
                    retrieval.get("distance_threshold_iteration", 0.6)
                ),
                rerank_threshold=(
                    float(retrieval["rerank_threshold"])
                    if retrieval.get("rerank_threshold") is not None
                    else None
                ),
                fallback_top_n=int(retrieval.get("fallback_top_n", 3)),
                final_top_k=(
                    settings.RERANK_TOP_K
                    if settings.RERANK_TOP_K is not None
                    else int(retrieval.get("final_top_k", 6))
                ),
                llm_reference_top_k=(
                    int(retrieval["llm_reference_top_k"])
                    if retrieval.get("llm_reference_top_k") is not None
                    else None
                ),
                hybrid_enabled=bool(retrieval.get("hybrid_enabled", False)),
                lexical_k=int(retrieval.get("lexical_k", 32)),
                rrf_k=int(retrieval.get("rrf_k", 60)),
                hybrid_pool_limit=int(retrieval.get("hybrid_pool_limit", 64)),
                kb_context_max_chars=int(retrieval.get("kb_context_max_chars", 12000)),
            ),
            evaluate=RagEvaluateConfig(
                context_max_chars=int(ev.get("context_max_chars", 3000)),
                pass_threshold=float(ev.get("pass_threshold", 0.75)),
                weights=RagEvaluateWeights(
                    relevance=wr,
                    groundedness=wg,
                    completeness=wc,
                ),
            ),
        )

    @functools.lru_cache(maxsize=1)
    def get_rerank_config(self) -> RerankConfig:
        """Get rerank config from `config/rerank.yaml` plus runtime flags."""
        data = load_rerank_raw()
        rerank = data.get("rerank", {}) or {}
        return RerankConfig(
            enabled=settings.RERANK_ENABLED,
            provider=(settings.RERANK_PROVIDER or rerank.get("provider", "bailian")),
            api_url=settings.RERANK_API_URL,
            model=rerank.get("model", "qwen3-rerank"),
            instruct=rerank.get(
                "instruct",
                "Given a web search query, retrieve relevant passages that answer the query.",
            ),
        )

    @functools.lru_cache(maxsize=1)
    def get_logging_config(self) -> LoggingConfig:
        """Get logging config from `config/logging.yaml`, overridable by env."""
        data = load_logging_raw()
        defaults = {
            "level": "INFO",
            "json": False,
            "to_file": True,
            "diagnose": False,
            "file": {
                "path": "logs/synapseflow.log",
                "rotation": "10 MB",
                "retention": "7 days",
            },
        }
        defaults.update(data.get("logging", {}))
        file_cfg = defaults.get("file", {}) or {}
        return LoggingConfig(
            level=settings.LOG_LEVEL or defaults["level"],
            json=settings.LOG_JSON if settings.LOG_JSON is not None else defaults["json"],
            log_to_file=settings.LOG_TO_FILE
            if settings.LOG_TO_FILE is not None
            else defaults["to_file"],
            diagnose=settings.LOG_DIAGNOSE
            if settings.LOG_DIAGNOSE is not None
            else defaults["diagnose"],
            file=LoggingFileConfig(
                path=file_cfg.get("path", "logs/synapseflow.log"),
                rotation=file_cfg.get("rotation", "10 MB"),
                retention=file_cfg.get("retention", "7 days"),
            ),
        )

    def get_repositories_config(self) -> Dict[str, Any]:
        """Get repository config from `config/repositories.yaml`."""
        return load_repositories_raw()

    @property
    def llm_configured(self) -> bool:
        """Return whether any configured LLM provider has an API key set."""
        data = load_models_raw()
        api_keys_mapping = data.get("api_keys", {})
        for env_var_name in api_keys_mapping.values():
            if getattr(settings, env_var_name, "").strip():
                return True
        return False


config_registry = ConfigRegistry()
