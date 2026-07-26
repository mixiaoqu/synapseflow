from pathlib import Path

from app.core.config.assistant_pages import (
    _load_page_config_data,
    get_assistant_page_config,
)
from app.core.config.loader import load_embed_app_pages_raw


def test_load_embed_app_pages_raw_merges_product_default_and_project_override(monkeypatch):
    default_path = Path("config/embed_pages/b2b/default/background.yaml")
    app_path = Path("config/embed_pages/b2b/demo/background.yaml")
    calls: list[Path] = []

    def fake_load_yaml(path: Path, default=None):
        calls.append(path)
        if path == default_path:
            return {
                "pages": {
                    "backgroundHome": {
                        "page_name": "B2B default page",
                        "page_description": "B2B default description",
                        "assistant_intro": "B2B default intro",
                        "suggested_questions": ["B2B default question"],
                    },
                    "sharedPage": {
                        "page_name": "Shared B2B page",
                    },
                }
            }
        if path == app_path:
            return {
                "pages": {
                    "backgroundHome": {
                        "page_description": "Project override description",
                        "suggested_questions": ["Project question 1", "Project question 2"],
                    }
                }
            }
        return default or {}

    monkeypatch.setattr("app.core.config.loader.load_yaml", fake_load_yaml)
    monkeypatch.setattr("app.core.config.loader.CONFIG_DIR", Path("config"))

    merged = load_embed_app_pages_raw("b2b", "demo", "background")

    assert merged == {
        "pages": {
            "backgroundHome": {
                "page_name": "B2B default page",
                "page_description": "Project override description",
                "assistant_intro": "B2B default intro",
                "suggested_questions": ["Project question 1", "Project question 2"],
            },
            "sharedPage": {
                "page_name": "Shared B2B page",
            },
        }
    }
    assert calls == [default_path, app_path]


def test_assistant_page_config_uses_product_default_and_project_override(monkeypatch):
    calls = []

    def fake_load(product_code: str, project_code: str, app_code: str):
        calls.append((product_code, project_code, app_code))
        return {
            "pages": {
                "backgroundHome": {
                    "page_name": "B2B default page",
                    "page_description": "Project override description",
                    "assistant_intro": "B2B default intro",
                    "suggested_questions": ["Project question 1", "Project question 2"],
                }
            }
        }

    monkeypatch.setattr("app.core.config.assistant_pages.load_embed_app_pages_raw", fake_load)
    _load_page_config_data.cache_clear()

    try:
        config = get_assistant_page_config("b2b", "demo", "background", "backgroundHome")
        assert config is not None
        assert config.page_name == "B2B default page"
        assert config.page_description == "Project override description"
        assert config.assistant_intro == "B2B default intro"
        assert config.suggested_questions == ["Project question 1", "Project question 2"]
        assert calls == [("b2b", "demo", "background")]
    finally:
        _load_page_config_data.cache_clear()
