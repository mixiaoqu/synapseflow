from app.core.config.registry import config_registry
from app.core.config.settings import Settings, settings


def test_graph_settings_default_to_safe_disabled_values(monkeypatch):
    monkeypatch.delenv("GRAPH_ENABLED", raising=False)
    monkeypatch.delenv("GRAPH_INDEXING_ENABLED", raising=False)
    monkeypatch.delenv("GRAPH_URI", raising=False)
    monkeypatch.delenv("GRAPH_USERNAME", raising=False)
    monkeypatch.delenv("GRAPH_PASSWORD", raising=False)
    monkeypatch.delenv("GRAPH_DATABASE", raising=False)
    cfg = Settings(_env_file=None)

    assert cfg.GRAPH_ENABLED is False
    assert cfg.GRAPH_INDEXING_ENABLED is False
    assert cfg.GRAPH_URI == "bolt://localhost:7687"
    assert cfg.GRAPH_USERNAME == "neo4j"
    assert cfg.GRAPH_PASSWORD == ""
    assert cfg.GRAPH_DATABASE == "neo4j"


def test_graph_config_reads_app_yaml_with_env_overrides(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.registry.load_app_raw",
        lambda: {
            "app": {},
            "graph": {
                "provider": "neo4j",
                "extraction_max_chars": 3200,
            },
        },
    )
    monkeypatch.setattr(settings, "GRAPH_URI", "bolt://graph:7687")
    monkeypatch.setattr(settings, "GRAPH_USERNAME", "graph-user")
    monkeypatch.setattr(settings, "GRAPH_PASSWORD", "graph-pass")
    monkeypatch.setattr(settings, "GRAPH_DATABASE", "synapseflow")
    monkeypatch.setattr(settings, "GRAPH_ENABLED", False)
    monkeypatch.setattr(settings, "GRAPH_INDEXING_ENABLED", False)
    config_registry.get_graph_config.cache_clear()

    try:
        config = config_registry.get_graph_config()
        assert config.enabled is False
        assert config.indexing_enabled is False
        assert config.provider == "neo4j"
        assert config.uri == "bolt://graph:7687"
        assert config.username == "graph-user"
        assert config.password == "graph-pass"
        assert config.database == "synapseflow"
        assert config.extraction_max_chars == 3200
    finally:
        config_registry.get_graph_config.cache_clear()
