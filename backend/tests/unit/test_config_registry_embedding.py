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

