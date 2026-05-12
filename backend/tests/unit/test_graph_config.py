from app.core.config.registry import config_registry
from app.core.config.settings import Settings, settings


def test_graph_settings_default_to_safe_disabled_values():
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
                "llm_model_role": "graph_extract",
                "extraction_max_chars": 3200,
            },
        },
    )
    monkeypatch.setattr(settings, "GRAPH_URI", "bolt://graph:7687")
    monkeypatch.setattr(settings, "GRAPH_USERNAME", "graph-user")
    monkeypatch.setattr(settings, "GRAPH_PASSWORD", "graph-pass")
    monkeypatch.setattr(settings, "GRAPH_DATABASE", "synapseflow")
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
        assert config.llm_model_role == "graph_extract"
        assert config.extraction_max_chars == 3200
    finally:
        config_registry.get_graph_config.cache_clear()
