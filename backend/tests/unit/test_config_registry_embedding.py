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

