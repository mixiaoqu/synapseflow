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
    RagRetrievalConfig,
    RerankConfig,
)
from .settings import settings


class ConfigRegistry:
    """Provides parsed, cached configuration objects."""

    @staticmethod
    def _get_provider_record(data: dict[str, Any], provider_id: str) -> dict[str, Any]:
        providers_cfg = data.get("providers", {}) or {}
        provider = providers_cfg.get(provider_id, {}) or {}
        if not provider:
            raise ValueError(f"Provider '{provider_id}' is not defined")
        return provider

    @staticmethod
    def _get_provider_api_key(provider: dict[str, Any], provider_id: str) -> str:
        api_key_env_name = str(provider.get("api_key_env") or "").strip()
        if not api_key_env_name:
            raise ValueError(f"Provider '{provider_id}' is missing api_key_env")
        api_key = getattr(settings, api_key_env_name, "").strip()
        if not api_key:
            raise ValueError(
                f"Provider '{provider_id}' API key is not configured "
                f"(environment variable: {api_key_env_name})"
            )
        return api_key

    @functools.lru_cache(maxsize=None)
    def get_model_asset(self, asset_key: str) -> ModelConfig:
        """Get one concrete chat model asset from `models.yaml`."""
        data = load_models_raw()
        assets_cfg = data.get("model_assets", {}) or {}
        raw = assets_cfg.get(asset_key, {}) or {}
        if not raw:
            raise ValueError(f"Model asset '{asset_key}' is not defined")

        if str(raw.get("type", "chat")) != "chat":
            raise ValueError(f"Model asset '{asset_key}' is not a chat model")

        provider_id = str(raw.get("provider") or "").strip()
        if not provider_id:
            raise ValueError(f"Model asset '{asset_key}' is missing provider")

        provider = self._get_provider_record(data, provider_id)
        api_key = self._get_provider_api_key(provider, provider_id)

        return ModelConfig(
            key=asset_key,
            model=str(raw.get("model", "gpt-4")),
            name=str(raw.get("name", asset_key)),
            provider=provider_id,
            api_key=api_key,
            api_base=str(provider.get("api_base", "")),
            temperature=(
                float(raw["temperature"])
                if raw.get("temperature") is not None
                else None
            ),
            request_timeout=int(raw.get("request_timeout", 120)),
            streaming=bool(raw.get("streaming", True)),
            max_tokens=int(raw["max_tokens"]) if raw.get("max_tokens") is not None else None,
        )

    @functools.lru_cache(maxsize=1)
    def list_model_assets(self) -> list[ModelConfig]:
        """List all configured chat model assets."""
        data = load_models_raw()
        assets_cfg = data.get("model_assets", {}) or {}
        items: list[ModelConfig] = []
        for asset_key, raw in assets_cfg.items():
            if str((raw or {}).get("type", "chat")) != "chat":
                continue
            items.append(self.get_model_asset(asset_key))
        return items

    @functools.lru_cache(maxsize=1)
    def get_app_config(self) -> AppConfig:
        """Get application-level settings from `config/app.yaml`."""
        data = load_app_raw()
        app = data.get("app", {}) or {}
        return AppConfig(
            project_name=app.get("project_name", "SynapseFlow"),
            version=app.get("version", "0.1.0"),
            description=app.get("description", "Agent collaboration system built with LangGraph"),
            api_v1_str=app.get("api_v1_str", "/api/v1"),
        )

    @functools.lru_cache(maxsize=None)
    def get_model_config(self, model_type: str) -> ModelConfig:
        """Get the default model asset for a given logical role."""
        data = load_models_raw()
        role_map = data.get("system_roles", {}) or {}
        asset_key = str(role_map.get(model_type) or "").strip()
        if not asset_key:
            raise ValueError(f"System role '{model_type}' is not defined")
        return self.get_model_asset(asset_key)

    @functools.lru_cache(maxsize=1)
    def get_embedding_config(self) -> EmbeddingConfig:
        """Get embedding config from `config/embedding.yaml`."""
        data = load_embedding_raw()
        emb = data.get("embedding", {}) or {}
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
        Get RAG-related config including chunking and retrieval.
        All values come from `config/embedding.yaml` and are cached in-process.
        """
        data = load_embedding_raw()
        chunk = data.get("chunk", {}) or {}
        retrieval = data.get("retrieval", {}) or {}

        return RagConfig(
            chunk=RagChunkConfig(
                size=int(chunk.get("size", 700)),
                overlap=int(chunk.get("overlap", 100)),
                parent_target_min=int(chunk.get("parent_target_min", 1200)),
                parent_target_max=int(chunk.get("parent_target_max", 2500)),
                child_target_min=int(chunk.get("child_target_min", 400)),
                child_target_max=int(chunk.get("child_target_max", 900)),
                split_overlap_units=int(chunk.get("split_overlap_units", 1)),
                parent_window_max_chars=int(chunk.get("parent_window_max_chars", 1800)),
                parent_window_neighbor_span=int(chunk.get("parent_window_neighbor_span", 1)),
            ),
            retrieval=RagRetrievalConfig(
                k_first=int(retrieval.get("k_first", 16)),
                distance_threshold=float(retrieval.get("distance_threshold", 0.5)),
                rerank_threshold=(
                    float(retrieval["rerank_threshold"])
                    if retrieval.get("rerank_threshold") is not None
                    else None
                ),
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
        )

    @functools.lru_cache(maxsize=1)
    def get_rerank_config(self) -> RerankConfig:
        """Get rerank config from `config/rerank.yaml` plus runtime flags."""
        data = load_rerank_raw()
        rerank = data.get("rerank", {}) or {}
        return RerankConfig(
            enabled=settings.RERANK_ENABLED,
            provider=(settings.RERANK_PROVIDER or rerank.get("provider", "local")),
            api_url=settings.RERANK_API_URL,
            model=rerank.get("model", "BAAI/bge-reranker-v2-m3"),
            instruct=rerank.get("instruct", ""),
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
        providers_cfg = data.get("providers", {}) or {}
        for provider in providers_cfg.values():
            env_var_name = str((provider or {}).get("api_key_env") or "").strip()
            if not env_var_name:
                continue
            if getattr(settings, env_var_name, "").strip():
                return True
        return False


config_registry = ConfigRegistry()
