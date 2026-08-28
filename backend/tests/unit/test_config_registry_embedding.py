from app.core.config.registry import config_registry
from app.core.config.settings import settings


def test_embedding_model_env_override(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.registry.load_embedding_raw",
        lambda: {
            "embedding": {
                "model": "BAAI/bge-m3",
                "dim": 1024,
                "device": "cpu",
                "batch_size": 32,
            }
        },
    )
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "C:/models/local-bge-m3")
    config_registry.get_embedding_config.cache_clear()

    try:
        config = config_registry.get_embedding_config()
        assert config.model == "C:/models/local-bge-m3"
        assert config.dim == 1024
    finally:
        monkeypatch.setattr(settings, "EMBEDDING_MODEL", None)
        config_registry.get_embedding_config.cache_clear()


def test_embedding_config_reads_siliconflow_runtime_settings(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.registry.load_embedding_raw",
        lambda: {
            "embedding": {
                "provider": "local",
                "model": "BAAI/bge-m3",
                "dim": 1024,
                "device": "cpu",
                "batch_size": 32,
            }
        },
    )
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "siliconflow")
    monkeypatch.setattr(settings, "EMBEDDING_API_URL", "https://api.siliconflow.cn/v1/embeddings")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "BAAI/bge-m3")
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSIONS", 1024)
    monkeypatch.setattr(settings, "SILICONFLOW_API_KEY", "sf-key")
    config_registry.get_embedding_config.cache_clear()

    try:
        config = config_registry.get_embedding_config()
        assert config.provider == "siliconflow"
        assert config.api_url == "https://api.siliconflow.cn/v1/embeddings"
        assert config.api_key == "sf-key"
        assert config.model == "BAAI/bge-m3"
        assert config.dimensions == 1024
    finally:
        config_registry.get_embedding_config.cache_clear()


def test_rag_chunk_config_reads_structured_chunk_fields(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.registry.load_embedding_raw",
        lambda: {
            "chunk": {
                "size": 700,
                "overlap": 100,
                "parent_target_min": 1100,
                "parent_target_max": 2100,
                "child_target_min": 350,
                "child_target_max": 850,
                "split_overlap_units": 2,
                "parent_window_max_chars": 1500,
                "parent_window_neighbor_span": 2,
            },
            "retrieval": {},
        },
    )
    config_registry.get_rag_config.cache_clear()

    try:
        config = config_registry.get_rag_config().chunk
        assert config.parent_target_min == 1100
        assert config.parent_target_max == 2100
        assert config.child_target_min == 350
        assert config.child_target_max == 850
        assert config.split_overlap_units == 2
        assert config.parent_window_max_chars == 1500
        assert config.parent_window_neighbor_span == 2
    finally:
        config_registry.get_rag_config.cache_clear()


def test_rag_retrieval_config_reads_profiles(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.registry.load_embedding_raw",
        lambda: {
            "chunk": {},
            "retrieval": {
                "k_first": 32,
                "distance_threshold": 0.5,
                "rrf_score_threshold": 0.02,
                "rerank_threshold": None,
                "final_top_k": 16,
                "llm_reference_top_k": 10,
                "hybrid_enabled": True,
                "lexical_k": 32,
                "rrf_k": 60,
                "hybrid_pool_limit": 64,
                "kb_context_max_chars": 16000,
                "profiles": {
                    "fast": {
                        "recall_k": 18,
                        "lexical_k": 12,
                        "graph_limit": 6,
                        "final_top_k": 8,
                        "llm_reference_top_k": 8,
                        "context_budget": 8000,
                        "rerank_enabled": False,
                    },
                    "standard": {
                        "recall_k": 32,
                        "lexical_k": 24,
                        "graph_limit": 10,
                        "final_top_k": 10,
                        "llm_reference_top_k": 10,
                        "context_budget": 12000,
                        "rerank_enabled": False,
                    },
                },
            },
        },
    )
    config_registry.get_rag_config.cache_clear()

    try:
        retrieval = config_registry.get_rag_config().retrieval
        assert retrieval.rrf_score_threshold == 0.02
        assert retrieval.profiles["fast"].recall_k == 18
        assert retrieval.profiles["fast"].graph_limit == 6
        assert retrieval.profiles["standard"].context_budget == 12000
        assert retrieval.profiles["standard"].rerank_enabled is False
    finally:
        config_registry.get_rag_config.cache_clear()

